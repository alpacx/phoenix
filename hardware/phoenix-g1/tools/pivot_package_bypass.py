"""Reorient individual local bypasses around their grounded land and verify each saved board."""
import hashlib,json,math,os,shutil,subprocess
from pathlib import Path
import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_preservation import verify_preservation
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
parent=json.loads((root/'layout-peripheral-supply-balls.json').read_text());current=root/parent['board']
assert hashlib.sha256(current.read_bytes()).hexdigest()==parent['sha256']
def group(b,q):return {k.m_Uuid.AsString() for k in b.GetConnectivity().GetConnectedItems(q)}
def face_of(q):return q.GetParentFootprint().GetLayer()
def label(q):return q.GetParentFootprint().GetReference()+'.'+q.GetNumber()
def mmvec(x,y):return p.VECTOR2I(round(x*1e6),round(y*1e6))
def segment(b,a,z,q):
    t=p.PCB_TRACK(b);t.SetLayer(face_of(q));t.SetNetCode(q.GetNetCode());t.SetWidth(500000);t.SetStart(a);t.SetEnd(z);return t
records=[];screened=0
for ref in [f'C{i}' for i in range(1601,1681)]+[f'C{i}' for i in range(2301,2310)]:
    b=p.LoadBoard(str(current));b.BuildConnectivity()
    cap=b.FindFootprintByReference(ref)
    if not cap:continue
    one,two=[cap.FindPadByNumber(n) for n in ('1','2')]
    if not one or not two or two.GetNetname()!='GND' or len(group(b,one))!=1:continue
    if b.FindFootprintByReference('C511').FindPadByNumber('2').m_Uuid.AsString() not in group(b,two):continue
    balls=[q for chip in ('U1','U2') for q in b.FindFootprintByReference(chip).Pads() if q.GetNetCode()==one.GetNetCode() and face_of(q)!=face_of(one) and (q.GetPosition()-two.GetPosition()).EuclideanNorm()<3500000]
    if not balls:continue
    start=two.GetPosition();face=cap.GetLayer();angle0=cap.GetOrientationDegrees()
    other=[f for f in b.GetFootprints() if f.GetReference()!=ref]
    obstacles=[k for k in [q for f in other for q in f.Pads()]+list(b.GetTracks()) if k.GetBoundingBox().Inflate(5000000).Contains(start)]
    courts=[f.GetCourtyard(face) for f in other if f.GetLayer()==face and f.GetBoundingBox(False,False).Inflate(5000000).Contains(start)]
    layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
    shapes={l:[k.GetEffectiveShape(l) for k in obstacles if k.IsOnLayer(l) and k.GetNetCode()!=one.GetNetCode()] for l in layers}
    candidates=[]
    for angle in (0,90,180,270):
        cap.SetOrientationDegrees(angle);cap.Move(start-two.GetPosition());xy=one.GetPosition()
        if any(cap.GetCourtyard(face).Collide(c,0) for c in courts):continue
        if any(one.GetEffectiveShape(face).Collide(s,200000) for s in shapes[face]):continue
        if any(two.GetEffectiveShape(face).Collide(k.GetEffectiveShape(face),200000) for k in obstacles if k.IsOnLayer(face) and k.GetNetCode()!=two.GetNetCode()):continue
        for dx,dy in ((0,0),(.025,0),(-.025,0),(0,.025),(0,-.025)):
            site=xy+mmvec(dx,dy)
            if not all(one.HitTest(site+mmvec(.275*math.cos(j*math.pi/32),.275*math.sin(j*math.pi/32))) for j in range(64)):continue
            via=p.PCB_VIA(b);via.SetWidth(550000);via.SetDrill(300000);via.SetPosition(site);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetViaType(p.VIATYPE_THROUGH);via.SetNetCode(one.GetNetCode());via.SetFillingMode(p.FILLING_MODE_FILLED);via.SetCappingMode(p.CAPPING_MODE_CAPPED)
            if any(via.GetEffectiveShape(l).Collide(s,200000) for l in layers for s in shapes[l]):continue
            if any(isinstance(k,p.PAD) and via.GetEffectiveShape(face_of(k)).Collide(k.GetEffectiveShape(face_of(k)),51000) for k in obstacles):continue
            if any(isinstance(k,p.PCB_VIA) and (k.GetPosition()-site).EuclideanNorm()<800000 for k in obstacles):continue
            for ball in balls:
                a=ball.GetPosition();delta=site-a;d=min(abs(delta.x),abs(delta.y));step=p.VECTOR2I(int(math.copysign(d,delta.x)),int(math.copysign(d,delta.y)))
                for corner in (a+step,site-step):
                    ts=[segment(b,i,j,ball) for i,j in ((a,corner),(corner,site)) if i!=j];length=sum(t.GetLength() for t in ts)
                    if length>2200000 or not ts or any(t.GetEffectiveShape(face_of(ball)).Collide(s,200000) for s in shapes[face_of(ball)] for t in ts):continue
                    candidates.append((length,angle,ball,ts,via))
    screened+=1
    for length,angle,ball,ts,via in sorted(candidates,key=lambda x:x[0]):
        cap.SetOrientationDegrees(angle);cap.Move(start-two.GetPosition())
        if screen(b):continue
        for k in ts+[via]:b.Add(k)
        folder=root/'runs'/('pivot-bypass-'+ref);folder.mkdir(exist_ok=True)
        for name in ('fp-lib-table','phy-joint.kicad_pro','phy-joint.kicad_dru'):shutil.copy2(current.parent/name,folder/name)
        out=folder/current.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
        if not introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text())):
            saved=p.LoadBoard(str(out));saved.BuildConnectivity();qq=saved.FindFootprintByReference(ref).FindPadByNumber('1')
            assert ball.m_Uuid.AsString() in group(saved,qq)
            assert not screen(saved)
            verify_preservation(p.LoadBoard(str(current)),saved)
            records.append(dict(pair=[label(one),label(ball)],angle_deg=angle,length_mm=length/1e6,via_nm=tuple(via.GetPosition())))
            current=out;break
        for k in ts+[via]:b.Remove(k)
(root/'pivot-package-bypass.json').write_text(json.dumps(dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),parent_sha256=parent['sha256'],screened=screened,records=records,assembly_ready=False),indent=2)+'\n')
print(screened,records,flush=True);os._exit(0)
