"""Escape the two PHY LDO strap pins to back-side resistors at ordinary through vias."""
from pathlib import Path
import hashlib,json,shutil,subprocess,os
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'phy-config-links.json').read_text())
current=root/cp['board']
assert hashlib.sha256(current.read_bytes()).hexdigest()==cp['sha256']
records=[]
for ref,chip,num,pin in [('R413','U4','7','2'),('R602','U6','11','2')]:
    base=p.LoadBoard(str(current));base.BuildConnectivity()
    b=p.LoadBoard(str(current));f=b.FindFootprintByReference(ref);phy=b.FindFootprintByReference(chip);q=phy.FindPadByNumber(num)
    if any(len(list(base.GetConnectivity().GetConnectedItems(k)))>1 for k in base.FindFootprintByReference(ref).Pads()):continue
    if f.GetLayer()==p.F_Cu:f.Flip(f.GetPosition(),False)
    assert q.GetNetCode()==f.FindPadByNumber(pin).GetNetCode()
    pos=q.GetPosition();sign=1 if pos.x>phy.GetPosition().x else -1
    toe=p.VECTOR2I((q.GetBoundingBox().GetRight() if sign>0 else q.GetBoundingBox().GetLeft())+sign*70000,pos.y)
    copper=list(b.GetTracks())+[k for g in b.GetFootprints() if g.GetReference()!=ref for k in g.Pads()]
    layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
    obstacles={l:[(k.GetNetCode(),k.GetEffectiveShape(l)) for k in copper if k.IsOnLayer(l) and k.GetBoundingBox().Inflate(5500000).Contains(toe)] for l in layers}
    def clear(k,l):
        shape=k.GetEffectiveShape(l)
        return all(n==k.GetNetCode() or not shape.Collide(s,200000) for n,s in obstacles[l])
    def trace(a,z,l):
        t=p.PCB_TRACK(b);t.SetStart(a);t.SetEnd(z);t.SetLayer(l);t.SetWidth(200000);t.SetNetCode(q.GetNetCode());return t
    options=sorted((dx*dx+dy*dy,dx,dy) for dx in range(3,31) for dy in range(-18,19))
    accepted=False
    for _,dx,dy in options:
        site=toe+p.VECTOR2I(sign*dx*100000,dy*100000)
        front=trace(toe,site,p.F_Cu)
        if not clear(front,p.F_Cu):continue
        v=p.PCB_VIA(b);v.SetPosition(site);v.SetWidth(450000);v.SetDrill(200000);v.SetNetCode(q.GetNetCode());v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu)
        if not all(clear(v,l) for l in layers):continue
        for a in (0,90,180,270):
            f.SetOrientationDegrees(a);one=f.FindPadByNumber(pin);two=f.FindPadByNumber('1' if pin=='2' else '2')
            delta=two.GetPosition()-one.GetPosition();unit=p.VECTOR2I(1 if delta.x>0 else -1 if delta.x<0 else 0,1 if delta.y>0 else -1 if delta.y<0 else 0)
            aim=site+p.VECTOR2I(unit.x*800000,unit.y*800000);f.Move(aim-one.GetPosition())
            if not all(clear(k,p.B_Cu) for k in (one,two)):continue
            area=f.GetCourtyard(p.B_Cu).BBox()
            if any(area.Intersects(g.GetCourtyard(p.B_Cu).BBox()) for g in b.GetFootprints() if g.GetReference()!=ref and g.GetLayer()==p.B_Cu):continue
            rear=trace(site,one.GetPosition(),p.B_Cu)
            if not clear(rear,p.B_Cu) or screen(b):continue
            for k in (front,rear,v):b.Add(k)
            folder=root/'runs'/('phy-config-back-'+ref);folder.mkdir(exist_ok=True)
            for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(current.parent/name,folder/name)
            dest=folder/current.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(dest),b)
            subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(dest)],check=True,stdout=subprocess.DEVNULL)
            delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
            saved=p.LoadBoard(str(dest));saved.BuildConnectivity();src=saved.FindFootprintByReference(chip).FindPadByNumber(num)
            if not delta and one.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(src)}:
                pres=verify_preservation(base,saved);records.append(dict(ref=ref,pin=num,via_nm=tuple(site),preservation=pres));current=dest;accepted=True;break
            for k in (front,rear,v):b.Remove(k)
        if accepted:break
    print(ref,accepted,flush=True)
(root/'phy-config-back.json').write_text(json.dumps(dict(board=str(current.relative_to(root)),sha256=hashlib.sha256(current.read_bytes()).hexdigest(),records=records),indent=2)+'\n')
os._exit(0)
