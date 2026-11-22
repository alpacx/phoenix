"""Locate local 1 µF capacitors on RK809 LDOs, screening both sides of the loop."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import os
import shutil
import subprocess
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'layout-exp-spi0-pullup.json').read_text());src=root/base['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
current=src;records=[];held=[];v=lambda xy:p.VECTOR2I(*xy);uid=lambda o:o.m_Uuid.AsString();side=p.F_Cu
def trial(ref):
    b=p.LoadBoard(str(current));b.BuildConnectivity();cap=b.FindFootprintByReference(ref);pmic=b.FindFootprintByReference('U4')
    positive=cap.FindPadByNumber('1');ground=cap.FindPadByNumber('2');pins=[q for q in pmic.Pads() if q.GetNetCode()==positive.GetNetCode()]
    if len(pins)!=1:return None,{'multiple_pmic_pins':len(pins)}
    pin=pins[0];center=tuple(pin.GetPosition());fc=pmic.GetPosition();box=pin.GetBoundingBox()
    contacts=[o for o in b.GetConnectivity().GetConnectedItems(positive) if isinstance(o,p.PAD) and uid(o)!=uid(positive)]
    if contacts:return None,{'existing_positive_contacts':len(contacts)}
    grounds={uid(o) for o in b.GetConnectivity().GetConnectedItems(pmic.FindPadByNumber('69'))}
    if cap.GetLayer()!=side:cap.Flip(cap.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
    near=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference()!=ref for q in f.Pads()] if inflated_box(o,5100000).Contains(v(center))]
    shapes=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in near if o.IsOnLayer(side)]
    holes=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    courts=[f.GetCourtyard(side) for f in b.GetFootprints() if f.GetReference()!=ref and f.GetLayer()==side and inflated_box(f,5000000).Contains(v(center))]
    keep=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
    targets={tuple(o.GetPosition()) for o in near if uid(o) in grounds and (isinstance(o,p.PCB_VIA) and o.GetDrillValue()>=200000 or isinstance(o,p.PAD) and o.GetDrillSize().x>=200000)}
    def clean(o):
        sh=o.GetEffectiveShape(side);bb=inflated_box(o,300000);nc=o.GetNetCode()
        return not any(c!=nc and bb.Intersects(box) and sh.Collide(s,202000) for c,s,box in shapes) and not any(c!=nc and sh.Collide(h,252000) for c,h in holes) and not any(sh.Collide(k,0) for k in keep)
    def wire(a,z,n,w):
        t=p.PCB_TRACK(b);t.SetStart(v(a));t.SetEnd(v(z));t.SetLayer(side);t.SetNetCode(n);t.SetWidth(w);return t
    def variants(a,z,n,w,others):
        dx=z[0]-a[0];dy=z[1]-a[1];dd=min(abs(dx),abs(dy));xx=int(math.copysign(dd,dx));yy=int(math.copysign(dd,dy))
        for c in ((a[0]+xx,a[1]+yy),(z[0]-xx,z[1]-yy)):
            ts=[wire(i,j,n,w) for i,j in zip((a,c),(c,z)) if i!=j]
            if all(clean(t) and not any(t.GetEffectiveShape(side).Collide(o.GetEffectiveShape(side),202000) for o in others) for t in ts):yield ts
    axis=0 if box.GetWidth()>box.GetHeight() else 1;sign=1 if center[axis]>tuple(fc)[axis] else -1
    toe=list(center);toe[axis]+=sign*((box.GetWidth() if axis==0 else box.GetHeight())//2-25000);toe=tuple(toe)
    necks=[]
    for start_offset in (0,40000,70000,90000,115000):
        start=list(toe);start[axis]+=sign*start_offset;start=tuple(start)
        for reach in (175000,275000,375000,475000,575000):
            elbow=list(toe);elbow[axis]+=sign*reach;elbow=tuple(elbow)
            lead=wire(start,elbow,pin.GetNetCode(),200000)
            if lead.GetEffectiveShape(side).Collide(pin.GetEffectiveShape(side),0) and clean(lead):necks.append((elbow,lead))
    counts=Counter(necks=len(necks))
    if not necks:return None,counts
    offsets=sorted(((x,y) for x in range(-30,31) for y in range(-30,31)),key=lambda xy:math.hypot(*xy));good=[]
    for x,y in offsets:
        xy=(toe[0]+x*100000,toe[1]+y*100000)
        if math.dist(xy,toe)>3200000:break
        for angle in (0,90,180,270):
            cap.SetOrientationDegrees(angle);cap.SetPosition(v(xy));court=cap.GetCourtyard(side)
            if any(court.Collide(c,100000) for c in courts) or not clean(positive) or not clean(ground):continue
            counts['bodies']+=1
            for elbow,lead in necks:
                for tail in variants(elbow,tuple(positive.GetPosition()),pin.GetNetCode(),400000,[ground]):
                    path=[lead]+tail;lp=sum(t.GetLength() for t in path)
                    if lp>3000000:continue
                    counts['positive_routes']+=1
                    for pt in sorted(targets,key=lambda z:math.dist(z,tuple(ground.GetPosition()))):
                        if math.dist(pt,tuple(ground.GetPosition()))>1600000:break
                        for ret in variants(tuple(ground.GetPosition()),pt,ground.GetNetCode(),400000,[positive]+path):
                            if not ret:continue
                            counts['two_land_routes']+=1;good.append((lp+sum(t.GetLength() for t in ret),xy,angle,path+ret))
                            break
                        else:continue
                        break
    seen=set();rejected=[]
    for length,xy,angle,ts in sorted(good,key=lambda r:r[0]):
        if (xy,angle) in seen:continue
        seen.add((xy,angle));cap.SetOrientationDegrees(angle);cap.SetPosition(v(xy))
        if screen(b):continue
        for t in ts:b.Add(t)
        folder=root/'runs'/('ldo-local-bank-'+ref);folder.mkdir(exist_ok=True);out=folder/src.name
        for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(current.parent/name,folder/name)
        p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
        delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
        if not delta:
            saved=p.LoadBoard(str(out));saved.BuildConnectivity();q1=saved.FindFootprintByReference(ref).FindPadByNumber('1');q2=saved.FindFootprintByReference(ref).FindPadByNumber('2')
            conn=lambda q:{uid(o) for o in saved.GetConnectivity().GetConnectedItems(q)}
            if uid(pin) in conn(q1) and uid(pmic.FindPadByNumber('69')) in conn(q2):
                proof=verify_preservation(p.LoadBoard(str(current)),saved)
                return out,dict(ref=ref,pin=pin.GetNumber(),center_nm=xy,angle=angle,loop_copper_mm=length/1e6,preservation=proof,new_drc=delta)
        rejected.append(delta)
        for t in ts:b.Remove(t)
        if len(seen)>=6:break
    return None,dict(counts=counts,rejected=rejected)
for ref in ('C460','C461','C462','C463','C464','C466','C467','C468'):
    saved,rec=trial(ref)
    if saved:records.append(rec);current=saved
    else:held.append(dict(ref=ref,result=rec))
(root/'ldo-local-bank-placement.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],sha256=hashlib.sha256(current.read_bytes()).hexdigest(),board=str(current.relative_to(root)),records=records,held=held,assembly_ready=False),indent=2)+'\n')
print(records,held,flush=True);os._exit(0)
