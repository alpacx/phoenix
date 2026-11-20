"""Add short off-pad capacitor returns to the existing ground plane in a cumulative PCB study."""
import hashlib,json,math,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
import sys
peripheral_bga='--outer-bga-ground' in sys.argv
compact='--core-interstitial' in sys.argv or peripheral_bga
core_ground='--core-ground' in sys.argv or compact
core_stage='outer-bga-ground' if peripheral_bga else 'core-ground-interstitial' if compact else 'core-ground-barrels'
peripheral='--peripheral-returns' in sys.argv
packages='--perimeter-barrels' in sys.argv
storage='--storage-ground' in sys.argv or packages
edges='--pad-edges' in sys.argv
fixtures='--fixture-clocks' in sys.argv
siblings='--grounded-pads' in sys.argv
resistors='--resistors' in sys.argv
reuse='--existing-vias' in sys.argv or siblings
cp=json.loads((root/('layout-core-ground-mesh.json' if peripheral_bga else 'layout-all-ground-surface.json' if core_ground else 'ground-package-perimeter.json' if packages else 'layout-regulator-joint.json' if peripheral else 'emmc-rail-inputs.json' if storage else 'fixture-clocks-ground.json' if edges else 'res-returns-verified.json' if fixtures else 'cap-grounded-pads.json' if resistors else 'cap-existing-vias.json' if siblings else 'cap-returns-verified.json' if reuse else 'pmic-control-bus.json')).read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
def anchor(board):return board.FindFootprintByReference('C511').FindPadByNumber('2')
ref_ground=anchor(b);connected={k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(ref_ground)}
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
candidates=[]
for f in b.GetFootprints():
    if core_ground:
        if f.GetReference() not in ({'U1','U2','U8001'} if peripheral_bga else {'U1'}):continue
    elif peripheral:
        if f.GetReference() not in {"U22","U23","J2001"}:continue
    elif storage:
        if f.GetReference() not in ({'U1','U2','U8001'} if packages else {'U8001'}):continue
        balls=[q.GetPosition() for q in f.Pads() if q.GetNumber()]
        xmin,xmax=min(q.x for q in balls)-350000,max(q.x for q in balls)+350000
        ymin,ymax=min(q.y for q in balls)-350000,max(q.y for q in balls)+350000
    elif fixtures:
        if f.GetReference() not in {'TP1','Y1','Y2002'}:continue
    elif not f.GetReference().startswith('R' if resistors else 'C'):continue
    for q in f.Pads():
        if core_ground and not peripheral_bga and not q.GetNumber().startswith('1'):continue
        if peripheral_bga and f.GetReference()=='U1' and q.GetNumber().startswith('1'):continue
        if q.GetNetCode()==ref_ground.GetNetCode() and q.m_Uuid.AsString() not in connected:
            candidates.append((f.GetReference(),q.GetNumber(),f.GetLayer()))
offsets=sorted(((x*50000,y*50000) for x in range(-19,20) for y in range(-19,20) if 0<x*x+y*y<=19**2),key=lambda v:math.hypot(*v))
accepted=[];held=[];current=src
for ref,num,layer in sorted(candidates):
    q=b.FindFootprintByReference(ref).FindPadByNumber(num);a=q.GetPosition();net=q.GetNetCode()
    if core_ground and q.m_Uuid.AsString() in connected:continue
    if packages:
        balls=[k.GetPosition() for k in q.GetParentFootprint().Pads() if k.GetNumber()]
        xmin,xmax=min(k.x for k in balls)-350000,max(k.x for k in balls)+350000
        ymin,ymax=min(k.y for k in balls)-350000,max(k.y for k in balls)+350000
        if xmin+350000<a.x<xmax-350000 and ymin+350000<a.y<ymax-350000:
            continue
    pads=[k for f in b.GetFootprints() for k in f.Pads() if k.GetBoundingBox().Inflate(1800000).Contains(a)]
    tracks=[k for k in b.GetTracks() if k.GetBoundingBox().Inflate(1800000).Contains(a)]
    shapes={l:[k.GetEffectiveShape(l) for k in pads+tracks if k.GetNetCode()!=net and k.IsOnLayer(l)] for l in layers}
    t=p.PCB_TRACK(b);t.SetStart(a);t.SetWidth(300000);t.SetLayer(layer);t.SetNetCode(net)
    v=p.PCB_VIA(b);v.SetWidth(600000);v.SetDrill(300000);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(net)
    if compact:
        v.SetWidth(450000);v.SetDrill(200000)
    if core_ground:
        nearby_ddr=[k.GetPosition() for k in pads if k.GetNetname().startswith('LPDDR4_')]
    sites=offsets
    if reuse:
        sites=sorted([(k.GetPosition().x-a.x,k.GetPosition().y-a.y) for k in tracks if isinstance(k,p.PCB_VIA) and k.IsOnLayer(layer) and k.m_Uuid.AsString() in connected and math.dist(tuple(k.GetPosition()),tuple(a))<=1200000],key=lambda off:math.hypot(*off))
    if siblings:
        sites=sorted([(k.GetPosition().x-a.x,k.GetPosition().y-a.y) for k in pads if k.IsOnLayer(layer) and k.m_Uuid.AsString() in connected and math.dist(tuple(k.GetPosition()),tuple(a))<=1000000],key=lambda off:math.hypot(*off))
    starts=[a]
    if peripheral:
        box=q.GetBoundingBox()
        starts=[p.VECTOR2I(round(box.GetLeft()+fx*box.GetWidth()),round(box.GetTop()+fy*box.GetHeight())) for fx in (.5,.15,.85) for fy in (.5,.15,.85)]
        starts=[start for start in starts if q.HitTest(start)]
    elif edges:
        starts=[a+p.VECTOR2I(x,y) for x in (-200000,-100000,0,100000,200000) for y in (-200000,-100000,0,100000,200000) if (x or y) and q.HitTest(a+p.VECTOR2I(x,y))]
    found=False
    for start in starts:
      for dx,dy in sites:
        t.SetStart(start)
        z=start+p.VECTOR2I(dx,dy)
        if core_ground and any(math.dist(tuple(z),tuple(ball))<1000000 for ball in nearby_ddr):continue
        if storage and xmin<z.x<xmax and ymin<z.y<ymax:continue
        if not reuse and any(zone.GetIsRuleArea() and zone.GetDoNotAllowVias() and zone.GetBoundingBox().Inflate(301000).Contains(z) for zone in b.Zones()):continue
        v.SetPosition(z)
        if compact:
            if any(v.GetEffectiveShape(k.GetLayer()).Collide(k.GetEffectiveShape(k.GetLayer()),51000) for k in pads):continue
        elif not reuse and any(k.GetBoundingBox().Inflate(351000).Contains(z) for k in pads):continue
        if not reuse and any(isinstance(k,p.PCB_VIA) and math.dist(tuple(k.GetPosition()),tuple(z))<800000 for k in tracks):continue
        v.SetPosition(z);t.SetEnd(z)
        if any(t.GetEffectiveShape(layer).Collide(s,200000) for s in shapes[layer]):continue
        if not reuse and any(v.GetEffectiveShape(l).Collide(s,200000) for l in layers for s in shapes[l]):continue
        found=True;break
      if found:break
    if not found:held.append(ref+'.'+num if storage else ref);continue
    b.Add(t)
    if not reuse:b.Add(v)
    accepted.append(dict(ref=ref,pad=num,via_nm=tuple(z),length_mm=t.GetLength()/1e6))
folder=root/('runs/'+core_stage if core_ground else 'runs/package-perimeter-barrels' if packages else 'runs/peripheral-returns' if peripheral else 'runs/storage-ground' if storage else 'runs/cap-edge-ground' if edges else 'runs/fixture-clock-ground' if fixtures else 'runs/res-ground' if resistors else 'runs/cap-ground-siblings' if siblings else 'runs/cap-ground-reuse' if reuse else 'runs/cap-ground-completion');folder.mkdir(exist_ok=True)
for file in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/file,folder/file)
out=folder/src.name
def verify():
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,stdout=subprocess.DEVNULL)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    return delta
delta=verify()
if delta:print(str(delta)[:3000],flush=True);raise RuntimeError('Inspect differential before accepting batch')
saved=p.LoadBoard(str(out));pres=verify_preservation(p.LoadBoard(str(src)),saved);assert not screen(saved)
ground={k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(anchor(saved))}
for row in accepted:assert saved.FindFootprintByReference(row['ref']).FindPadByNumber(row['pad']).m_Uuid.AsString() in ground,row
if not accepted:out=src
(root/(core_stage+'.json' if core_ground else 'package-perimeter-barrels.json' if packages else 'peripheral-returns.json' if peripheral else 'storage-ground.json' if storage else 'cap-edge-ground.json' if edges else 'fixture-clocks-ground.json' if fixtures else 'res-returns-verified.json' if resistors else 'cap-grounded-pads.json' if siblings else 'cap-existing-vias.json' if reuse else 'cap-returns-verified.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],added=accepted,unresolved=held,preservation=pres,new_drc=delta,assembly_ready=False),indent=2)+'\n')
print(len(accepted),len(held),flush=True);os._exit(0)
