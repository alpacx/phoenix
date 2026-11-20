"""Fit the eMMC clock series termination at M25 without changing the board's DRC rules."""
import hashlib,json,math,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
prior=json.loads((root/'layout-opposite-bypass.json').read_text());src=root/prior['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==prior['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
cpu=b.FindFootprintByReference('U1');q=cpu.FindPadByNumber('M25');r=b.FindFootprintByReference('R8004')
one=r.FindPadByNumber('1');two=r.FindPadByNumber('2');net=one.GetNetCode()
copper_ids={t.m_Uuid.AsString() for t in b.GetTracks()}
assert q.GetNetCode()==net and r.GetLayer()==p.B_Cu
assert all(not any(k.m_Uuid.AsString() in copper_ids for k in b.GetConnectivity().GetConnectedItems(pad)) for pad in r.Pads())
origin=q.GetPosition();loc=r.GetPosition()
others=[f for f in b.GetFootprints() if f.GetReference()!='R8004']
pads=[k for f in others for k in f.Pads() if k.GetBoundingBox().Inflate(5000000).Contains(origin)]
tracks=[t for t in b.GetTracks() if t.GetBoundingBox().Inflate(5000000).Contains(origin)]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
obs={l:[(k.GetNetCode(),k.GetEffectiveShape(l),76200 if isinstance(k,p.PAD) and k.GetParentFootprint().GetReference()=='U1' else 200000) for k in pads+tracks if k.IsOnLayer(l)] for l in layers}
def free(k,l):
    shape=k.GetEffectiveShape(l)
    return all(n==k.GetNetCode() or not shape.Collide(o,clearance) for n,o,clearance in obs[l])
def track(a,z):
    t=p.PCB_TRACK(b);t.SetStart(a);t.SetEnd(z);t.SetWidth(200000);t.SetNetCode(net);t.SetLayer(p.F_Cu);return t
courts=[f.GetCourtyard(p.B_Cu).BBox() for f in others if f.GetLayer()==p.B_Cu]
sites=0;opts=[]
for dx in range(-22,23):
 for dy in range(-22,23):
    pos=origin+p.VECTOR2I(dx*50000,dy*50000)
    if math.dist(tuple(pos),tuple(origin))>1100000:continue
    via=p.PCB_VIA(b);via.SetWidth(450000);via.SetDrill(200000);via.SetPosition(pos);via.SetNetCode(net);via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu)
    if any(k.GetEffectiveShape(k.GetLayer()).Collide(via.GetEffectiveShape(k.GetLayer()),50000) for k in pads):continue
    if any(isinstance(k,p.PCB_VIA) and math.dist(tuple(k.GetPosition()),tuple(pos))<(k.GetDrillValue()+200000)/2+250000 for k in tracks):continue
    if not all(free(via,l) for l in layers):continue
    sites+=1
    x,y=pos-origin;d=min(abs(x),abs(y));vec=p.VECTOR2I(int(math.copysign(d,x)),int(math.copysign(d,y)))
    for corner in (origin+vec,pos-vec):
        lines=[track(a,z) for a,z in ((origin,corner),(corner,pos)) if a!=z]
        if not all(free(t,p.F_Cu) for t in lines):continue
        for angle in (0,90,180,270):
            r.SetOrientationDegrees(angle);r.Move(pos-one.GetPosition())
            if any(c.Intersects(r.GetCourtyard(p.B_Cu).BBox()) for c in courts) or not all(free(k,p.B_Cu) for k in r.Pads()):continue
            if any(not one.HitTest(pos+p.VECTOR2I(round(250000*math.cos(i*math.pi/32)),round(250000*math.sin(i*math.pi/32)))) for i in range(64)):continue
            opts.append((sum(t.GetLength() for t in lines),math.dist(tuple(r.GetPosition()),tuple(loc)),angle,tuple(r.GetPosition()),via,lines))
folder=root/'runs/emmc-source-r';folder.mkdir(exist_ok=True)
for name in ('fp-lib-table','phy-joint.kicad_pro','phy-joint.kicad_dru'):shutil.copy2(src.parent/name,folder/name)
rec=None
for length,_,angle,center,via,lines in sorted(opts,key=lambda o:o[:2])[:20]:
    r.SetOrientationDegrees(angle);r.SetPosition(p.VECTOR2I(*center))
    if screen(b):continue
    via.SetFillingMode(p.FILLING_MODE_FILLED);via.SetCappingMode(p.CAPPING_MODE_CAPPED)
    for item in [via]+lines:b.Add(item)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if not delta:
        saved=p.LoadBoard(str(out));verify_preservation(p.LoadBoard(str(src)),saved)
        assert one.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('U1').FindPadByNumber('M25'))}
        rec=dict(pair=['R8004.1','U1.M25'],via_nm=tuple(via.GetPosition()),source_length_mm=length/1e6);break
    for item in [via]+lines:b.Remove(item)
if not rec:out=src
(root/'emmc-source-r.json').write_text(json.dumps(dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=prior['sha256'],barrel_sites=sites,placements=len(opts),change=rec,assembly_ready=False),indent=2)+'\n')
print(sites,len(opts),rec,flush=True);os._exit(0)
