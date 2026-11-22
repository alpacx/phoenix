"""Place the existing SDIO pull-ups near the module and keep short local signal taps."""
from pathlib import Path
import hashlib
import json
import math
import os
import shutil
import subprocess
import pcbnew as p
from pcb_bounds import inflated_box
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-aux-cap-banks.json').read_text())
src=root/meta['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
current=src
records=[]
held=[]
for ref in ('R2012','R2013','R2014','R2010','R2011'):
    b=p.LoadBoard(str(current));b.BuildConnectivity()
    res=b.FindFootprintByReference(ref)
    assert all(not b.GetConnectivity().GetConnectedTracks(q) for q in res.Pads())
    module=b.FindFootprintByReference('U25')
    one=res.FindPadByNumber('1')
    pin=next(q for q in module.Pads() if q.GetNetCode()==one.GetNetCode())
    loc=pin.GetPosition()
    layer=p.B_Cu
    res.Flip(res.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
    assert res.GetLayer()==layer
    one=res.FindPadByNumber('1');two=res.FindPadByNumber('2')
    others=[f for f in b.GetFootprints() if f.GetReference()!=ref and inflated_box(f,5400000).Contains(loc)]
    courts=[f.GetCourtyard(layer).BBox() for f in others if f.GetLayer()==layer]
    objects=[k for k in list(b.GetTracks())+[q for f in others for q in f.Pads()] if k.IsOnLayer(layer) and inflated_box(k,5400000).Contains(loc)]
    shapes=[(k.GetNetCode(),k.GetEffectiveShape(layer),k.GetBoundingBox()) for k in objects]
    holes=[(k.GetNetCode(),k.GetEffectiveHoleShape()) for k in objects if isinstance(k,p.PCB_VIA)]
    def free(k):
        sh=k.GetEffectiveShape(layer)
        bb=inflated_box(k,250000)
        return not any(n!=k.GetNetCode() and bb.Intersects(box) and sh.Collide(s,202000) for n,s,box in shapes) and not any(n!=k.GetNetCode() and sh.Collide(s,250000) for n,s in holes)
    def lines(start,end,variant):
        delta=end-start
        d=min(abs(delta.x),abs(delta.y))
        diag=p.VECTOR2I(int(math.copysign(d,delta.x)),int(math.copysign(d,delta.y)))
        c=(start+diag,end-diag)[variant]
        segs=[]
        for u,v in ((start,c),(c,end)):
            if u==v:continue
            t=p.PCB_TRACK(b);t.SetLayer(layer);t.SetWidth(200000);t.SetNetCode(pin.GetNetCode());t.SetStart(u);t.SetEnd(v);segs.append(t)
        return segs
    candidates=[]
    for angle in (90,270,0,180):
        res.SetOrientationDegrees(angle)
        for xx in range(-32,33):
            for yy in range(5,36):
                pos=loc+p.VECTOR2I(xx*100000,yy*100000)
                res.SetPosition(pos)
                box=res.GetCourtyard(layer).BBox()
                if any(box.Intersects(c) for c in courts):continue
                if not free(one) or not free(two):continue
                start=loc
                for key in (0,1):
                    path=lines(start,one.GetPosition(),key)
                    length=sum(t.GetLength() for t in path)
                    if 0<length<=3000000 and all(free(t) and not t.GetEffectiveShape(layer).Collide(two.GetEffectiveShape(layer),202000) for t in path):
                        candidates.append((length,angle,tuple(pos),key))
    ok=False
    folder=root/'runs'/('wifi-bias-'+ref)
    folder.mkdir(exist_ok=True)
    for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(current.parent/name,folder/name)
    # Check the shortest distinct placements, then keep the shortest passing branch.
    poses=set()
    for length,angle,pos,key in sorted(candidates):
        if (angle,pos) in poses:continue
        poses.add((angle,pos))
        res.SetOrientationDegrees(angle);res.SetPosition(p.VECTOR2I(*pos))
        if screen(b):continue
        tracks=lines(loc,one.GetPosition(),key)
        for t in tracks:b.Add(t)
        out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
        delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
        if not delta:
            saved=p.LoadBoard(str(out));saved.BuildConnectivity()
            verify_preservation(p.LoadBoard(str(current)),saved);assert not screen(saved)
            a=saved.FindFootprintByReference(ref).FindPadByNumber('1')
            z=saved.FindFootprintByReference('U25').FindPadByNumber(pin.GetNumber())
            assert z.m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(a)}
            records.append(dict(pair=[ref+'.1','U25.'+pin.GetNumber()],pos_nm=pos,angle_deg=angle,length_mm=length/1e6,net=pin.GetNetname()))
            current=out;ok=True;break
        for t in tracks:b.Remove(t)
        if len(poses)>=10:break
    if not ok:held.append(dict(ref=ref,geometric_poses=len(candidates),tested=len(poses)))
(root/'wifi-sdio-bias.json').write_text(json.dumps(dict(parent_sha256=meta['sha256'],sha256=hashlib.sha256(current.read_bytes()).hexdigest(),board=str(current.relative_to(root)),records=records,held=held,assembly_ready=False),indent=2)+'\n')
print(records,held,flush=True)
os._exit(0)
