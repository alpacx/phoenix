"""Try C8003 on the opposite face at the outer VCCQ balls with two local off-pad vias."""
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
import sys
vddi='--vddi' in sys.argv
ref='C8001' if vddi else 'C8003'
same='--same-face' in sys.argv
cp=json.loads((root/('layout-regulator-banks.json' if vddi else 'emmc-local-bypass.json' if same else 'storage-ground.json')).read_text());source=root/cp['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(source));baseline=p.LoadBoard(str(source));b.BuildConnectivity();cap=b.FindFootprintByReference(ref);memory=b.FindFootprintByReference('U8001')
assert len(list(b.GetConnectivity().GetConnectedItems(cap.FindPadByNumber('1'))))==1
old_ids={'b8deed8c-0bc9-4cc7-85c1-19526fc957e1','3276a09c-825b-4970-a7a5-538e122922a7','8948b8d7-a625-4e1b-a85a-ff08f6623c6f','9437b719-28c4-451f-9d5d-d07f52f48834','ca5ae2a8-63b9-4646-9e50-09e33e4e784c','cc010a84-3eef-449b-9e2b-47dbb4c18706'}
if vddi:
    ground=cap.FindPadByNumber('2')
    branch=[k for k in b.GetTracks() if k.GetNetname()=='GND' and k.IsOnLayer(cap.GetLayer()) and not isinstance(k,p.PCB_VIA) and (ground.HitTest(k.GetStart()) or ground.HitTest(k.GetEnd()))]
    assert len(branch)==2
    old_ids={k.m_Uuid.AsString() for k in branch}
    for k in b.GetTracks():
        if isinstance(k,p.PCB_VIA) and k.GetNetname()=='GND' and any(k.GetPosition()==pt for t in branch for pt in (t.GetStart(),t.GetEnd())):
            old_ids.add(k.m_Uuid.AsString())
old=[t for t in b.GetTracks() if t.m_Uuid.AsString() in old_ids]
assert len(old)==len(old_ids) and all(t.GetNetname()=='GND' for t in old)
for item in old:b.Remove(item)
if not same:cap.Flip(cap.GetPosition(),False)
face=cap.GetLayer()
rail=cap.FindPadByNumber('1');gnd=cap.FindPadByNumber('2')
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
anchor=memory.FindPadByNumber('C2' if vddi else 'P5').GetPosition()
others=[f for f in b.GetFootprints() if f.GetReference()!=ref]
near=lambda k:k.GetBoundingBox().Inflate(7000000).Contains(anchor)
pads=[k for f in others for k in f.Pads() if near(k)]
objects=pads+[k for k in b.GetTracks() if near(k)]
boxes=[f.GetCourtyard(face).BBox() for f in others if f.GetLayer()==face and f.GetCourtyard(face).BBox().Inflate(7000000).Contains(anchor)]
shapes={l:[(k.GetNetCode(),k.GetEffectiveShape(l)) for k in objects if k.IsOnLayer(l)] for l in layers}
pad_keep=[q.GetBoundingBox().Inflate(351000) for q in pads]
def free(k,l):
    shape=k.GetEffectiveShape(l);return all(n==k.GetNetCode() or not shape.Collide(s,200000) for n,s in shapes[l])
def via(site,net):
    v=p.PCB_VIA(b);v.SetWidth(600000);v.SetDrill(300000);v.SetPosition(site);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetViaType(p.VIATYPE_THROUGH);v.SetNetCode(net);return v
def trace(a,z,l,net):
    t=p.PCB_TRACK(b);t.SetStart(a);t.SetEnd(z);t.SetWidth(300000);t.SetLayer(l);t.SetNetCode(net);return t
def clear_via(v):
    return not any(box.Contains(v.GetPosition()) for box in pad_keep) and all(free(v,l) for l in layers)
def offset(dx,dy):return p.VECTOR2I(dx*100000,dy*100000)
record=None;feasible=[];sites=0;positions=0
for num in (('C2',) if vddi else ('P5','P3')):
    ball=memory.FindPadByNumber(num);start=ball.GetPosition()
    if same:
        for dx in range(-18,19,2):
          for dy in (range(-22,23,2) if vddi else range(-40,-5,2)):
            site=start+offset(dx,dy)
            if math.dist(tuple(start),tuple(site))>4000000:continue
            for angle in (0,90,180,270):
                cap.SetOrientationDegrees(angle);cap.Move(site-rail.GetPosition())
                if any(cap.GetCourtyard(face).BBox().Intersects(box) for box in boxes):continue
                spur=trace(start,site,face,rail.GetNetCode())
                if not all(free(k,face) for k in (rail,gnd,spur)) or spur.GetEffectiveShape(face).Collide(gnd.GetEffectiveShape(face),200000):continue
                positions+=1
                for jx,jy in ((8,0),(-8,0),(0,8),(0,-8),(7,5),(7,-5),(-7,5),(-7,-5),(5,7),(-5,7),(5,-7),(-5,-7)):
                    gs=gnd.GetPosition()+offset(jx,jy);gv=via(gs,gnd.GetNetCode());gt=trace(gnd.GetPosition(),gs,face,gnd.GetNetCode())
                    if any(q.GetBoundingBox().Inflate(351000).Contains(gs) for q in (rail,gnd)) or not clear_via(gv) or not free(gt,face):continue
                    if any(k.GetEffectiveShape(face).Collide(other.GetEffectiveShape(face),200000) for k in (gv,gt) for other in (rail,spur)):continue
                    feasible.append((spur.GetLength()+gt.GetLength(),num,angle,tuple(cap.GetPosition()),tuple(site),tuple(gs)))
        continue
    for dx in range(-11,12):
      for dy in (range(-12,13) if vddi else range(-12,-3)):
        if math.hypot(dx,dy)>12:continue
        site=start+offset(dx,dy);v=via(site,rail.GetNetCode());spur=trace(start,site,p.B_Cu,rail.GetNetCode())
        if not clear_via(v) or not free(spur,p.B_Cu):continue
        sites+=1
        for angle in (0,90,180,270):
          cap.SetOrientationDegrees(angle)
          for ix,iy in ((8,0),(-8,0),(0,8),(0,-8),(7,5),(7,-5),(-7,5),(-7,-5),(5,7),(-5,7),(5,-7),(-5,-7)):
            cap.Move(site+offset(ix,iy)-rail.GetPosition())
            if any(cap.GetCourtyard(p.F_Cu).BBox().Intersects(box) for box in boxes):continue
            if any(q.GetBoundingBox().Inflate(351000).Contains(site) for q in (rail,gnd)):continue
            top=trace(site,rail.GetPosition(),p.F_Cu,rail.GetNetCode())
            if not all(free(k,p.F_Cu) for k in (rail,gnd,top)):continue
            if top.GetEffectiveShape(p.F_Cu).Collide(gnd.GetEffectiveShape(p.F_Cu),200000):continue
            positions+=1
            for jx,jy in ((8,0),(-8,0),(0,8),(0,-8),(7,5),(7,-5),(-7,5),(-7,-5),(5,7),(-5,7),(5,-7),(-5,-7)):
                gs=gnd.GetPosition()+offset(jx,jy);gv=via(gs,gnd.GetNetCode());gt=trace(gnd.GetPosition(),gs,p.F_Cu,gnd.GetNetCode())
                if any(q.GetBoundingBox().Inflate(351000).Contains(gs) for q in (rail,gnd)) or math.dist(tuple(gs),tuple(site))<810000:continue
                if not clear_via(gv) or not free(gt,p.F_Cu):continue
                if any(k.GetEffectiveShape(p.F_Cu).Collide(other.GetEffectiveShape(p.F_Cu),200000) for k in (gt,gv) for other in (rail,top,v)):continue
                feasible.append((spur.GetLength()+top.GetLength()+gt.GetLength(),num,angle,tuple(cap.GetPosition()),tuple(site),tuple(gs)))
folder=root/('runs/emmc-vddi-same' if vddi and same else 'runs/emmc-vddi-opposite' if vddi else 'runs/emmc-vccq-ball-cap' if same else 'runs/emmc-vccq-local-bypass');folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source.parent/name,folder/name)
for _,num,angle,center,site,gs in sorted(feasible)[:12]:
    cap.SetOrientationDegrees(angle);cap.SetPosition(p.VECTOR2I(*center));s=p.VECTOR2I(*site);g=p.VECTOR2I(*gs)
    items=[via(s,rail.GetNetCode()),via(g,gnd.GetNetCode()),trace(memory.FindPadByNumber(num).GetPosition(),s,p.B_Cu,rail.GetNetCode()),trace(s,rail.GetPosition(),p.F_Cu,rail.GetNetCode()),trace(gnd.GetPosition(),g,p.F_Cu,gnd.GetNetCode())]
    if same:items=[via(g,gnd.GetNetCode()),trace(memory.FindPadByNumber(num).GetPosition(),rail.GetPosition(),face,rail.GetNetCode()),trace(gnd.GetPosition(),g,face,gnd.GetNetCode())]
    for item in items:b.Add(item)
    out=folder/source.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((source.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if not delta:
        saved=p.LoadBoard(str(out));pres=verify_preservation(baseline,saved,replaced_copper=old_ids);assert not screen(saved)
        cap1=saved.FindFootprintByReference(ref).FindPadByNumber('1')
        assert memory.FindPadByNumber(num).m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(cap1)}
        record=dict(pair=[ref+'.1','U8001.'+num],center_nm=center,vccq_via_nm=None if same else site,ground_via_nm=gs,preservation=pres);break
    for item in items:b.Remove(item)
if not record:out=source
(root/('emmc-vddi-same.json' if vddi and same else 'emmc-vddi-opposite.json' if vddi else 'emmc-ball-cap.json' if same else 'emmc-local-bypass.json')).write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),change=record,clear_ball_via_sites=sites,clear_surface_positions=positions,testable_geometries=len(feasible),assembly_ready=False),indent=2)+'\n')
print(sites,positions,len(feasible),bool(record),flush=True);os._exit(0)
