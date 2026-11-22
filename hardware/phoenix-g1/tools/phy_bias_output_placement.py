"""Check a coupled output-capacitor and bias-resistor move at the PHY pin-39 edge."""
from pathlib import Path
import hashlib
import json
import math
import os
import pcbnew as p
from pcb_bounds import inflated_box

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'layout-ground-island-barrels.json').read_text())
src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src))
cap=b.FindFootprintByReference('C511')
res=b.FindFootprintByReference('R513')
pin=b.FindFootprintByReference('U5').FindPadByNumber('39')
one,two=[cap.FindPadByNumber(n) for n in ('1','2')]
origin=cap.GetPosition()
oldpad=one.GetPosition()
bulk=b.FindFootprintByReference('C2201')
bulk_origin=bulk.GetPosition()
others=[f for f in b.GetFootprints() if f.GetReference() not in ('R513','C511','C2201') and f.GetLayer()==p.F_Cu and inflated_box(f,6000000).Contains(origin)]
courts=[f.GetCourtyard(p.F_Cu).BBox() for f in others]
obstacles=[o for o in list(b.GetTracks())+[q for f in others for q in f.Pads()] if o.IsOnLayer(p.F_Cu) and inflated_box(o,6000000).Contains(origin)]
def object_name(o):
    if isinstance(o,p.PAD):return o.GetParentFootprint().GetReference()+'.'+o.GetNumber()
    return o.GetNetname()
def collisions(o,exclude):
    return {object_name(k) for k in obstacles if k.GetNetname() not in exclude and k.GetNetCode()!=o.GetNetCode() and o.GetEffectiveShape(p.F_Cu).Collide(k.GetEffectiveShape(p.F_Cu),200000)}
def track(u,z,width,net):
    t=p.PCB_TRACK(b)
    t.SetStart(u)
    t.SetEnd(z)
    t.SetLayer(p.F_Cu)
    t.SetWidth(width)
    t.SetNetCode(net)
    return t
choices={}
clear_poses=0
accepted_bulk=[]
# Keep the existing output pad feed, its two barrels and both ground barrels.
# The extension is screened at the original trunk width.
for shift in range(-600000,-1300001,-50000):
    cap.SetPosition(origin+p.VECTOR2I(shift,0))
    cb=cap.GetCourtyard(p.F_Cu).BBox()
    if any(cb.Intersects(c) for c in courts):continue
    for bx,by in ((ix,t) for t in (0,-250000,250000,-500000,500000,-750000,750000) for ix in range(0,-1000001,-50000)):
        bulk.SetPosition(bulk_origin+p.VECTOR2I(bx,by))
        abb=bulk.GetCourtyard(p.F_Cu).BBox()
        if not cb.Intersects(abb) and not any(abb.Intersects(c) for c in courts):break
    else:continue
    accepted_bulk.append((shift,bx,by))
    feed=track(oldpad,one.GetPosition(),1550000,one.GetNetCode())
    cbad=set().union(*(collisions(q,set()) for q in bulk.Pads()))|collisions(feed,set())|collisions(one,set())|collisions(two,set())
    for angle in (0,180):
        res.SetOrientationDegrees(angle)
        for x in range(58500000,59500001,50000):
            for y in range(31950000,32650001,50000):
                res.SetPosition(p.VECTOR2I(x,y))
                rb=res.GetCourtyard(p.F_Cu).BBox()
                if cb.Intersects(rb) or any(rb.Intersects(c) for c in courts):continue
                clear_poses+=1
                a,z=[res.FindPadByNumber(n) for n in ('1','2')]
                toe=pin.GetPosition()+p.VECTOR2I(-250000,0)
                wire=track(toe,a.GetPosition(),200000,a.GetNetCode())
                names=cbad|collisions(a,set())|collisions(z,set())|collisions(wire,set())
                if wire.GetEffectiveShape(p.F_Cu).Collide(z.GetEffectiveShape(p.F_Cu),200000):continue
                ends=(a.GetPosition()-toe).EuclideanNorm()/1e6
                key=tuple(sorted(names))
                entry=dict(bulk_shift_mm=[bx/1e6,by/1e6],cap_shift_mm=shift/1e6,res_pos_nm=[x,y],orientation=angle,signal_length_mm=ends)
                if key not in choices or (abs(shift/1e6),ends)<(abs(choices[key]['cap_shift_mm']),choices[key]['signal_length_mm']):choices[key]=entry
report=dict(parent_sha256=cp['sha256'],cap_bulk_clearances_nm=accepted_bulk,courtyard_poses=clear_poses,trials=[dict(blockers=list(k),**v) for k,v in sorted(choices.items(),key=lambda it:(len(it[0]),abs(it[1]['cap_shift_mm'])))],adopted=False)
(root/'phy-bias-output-placement.json').write_text(json.dumps(report,indent=2)+'\n')
print(clear_poses,report['trials'][:3],flush=True)
os._exit(0)
