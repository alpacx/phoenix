"""Locate an ordinary capacitor-branch barrel for the bonded six-ball VDD_CPU cluster."""
from pathlib import Path
from collections import Counter
import hashlib
import math
import sys
import json

import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import barrel,make

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
rail="--second-barrel" in sys.argv
ball=next((s.split("=",1)[1] for s in sys.argv if s.startswith("--rail-ball=")),None)
cp=json.loads((root/("layout-ground-copper-contact.json" if "--current-io" in sys.argv else "layout-bga-ground-qualified.json" if ball else "layout-cpu-local-hf-bypass.json" if rail else "layout-bga-referenced-barrel.json")).read_text())
file=root/cp["board"];assert hashlib.sha256(file.read_bytes()).hexdigest()==cp["sha256"]
b=p.LoadBoard(str(file));b.BuildConnectivity()
cells="--pitch-centers" in sys.argv
lift="--lift-ground" in sys.argv
if lift:
    barrier=next(t for t in b.GetTracks() if t.m_Uuid.AsString()=="5b43d5da-3484-47e8-bc7d-22355cba3a8f")
    b.Remove(barrier);b.BuildConnectivity()
soc=b.FindFootprintByReference("U1")
anchor=soc.FindPadByNumber(ball) if ball else None
lands=[q for q in soc.Pads() if q.GetNetname()==(anchor.GetNetname() if ball else "VDD_CPU")]
if ball:
    domain={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(anchor)}
    lands=[q for q in lands if q.m_Uuid.AsString() in domain or q.GetNumber()==ball]
gndcode=b.FindNet("GND").GetNetCode();code=lands[0].GetNetCode()
ids={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(lands[0])}
assert all(q.m_Uuid.AsString() in ids for q in lands)
existing=[t for t in b.GetTracks() if t.m_Uuid.AsString() in ids and not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu]
seeds={tuple(q.GetPosition()) for q in lands}
for t in existing:
    a,z=tuple(t.GetStart()),tuple(t.GetEnd())
    for i in range(11):seeds.add(tuple(round(u+(v-u)*i/10) for u,v in zip(a,z)))
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
center=anchor.GetPosition() if ball else p.VECTOR2I(42400000,20000000)
items=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if inflated_box(o,4600000).Contains(center)]
def tag(o):
    return (o.GetParentFootprint().GetReference()+"."+o.GetNumber()) if isinstance(o,p.PAD) else o.GetNetname()
def bbox(o):return o.GetBoundingBox()
shapes=[(o,o.GetEffectiveShape(l),bbox(o),b.GetLayerName(l)) for l in layers for o in items if o.IsOnLayer(l) and o.GetNetCode()!=code]
pads=[(q,q.GetEffectiveShape(q.GetParentFootprint().GetLayer()),bbox(q)) for q in items if isinstance(q,p.PAD)]
holes=[(o,o.GetEffectiveHoleShape(),bbox(o)) for o in items if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
front=[(o,geo,box) for o,geo,box,l in shapes if l=="F.Cu"]
zones=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
guards={};stats=Counter();singles=Counter();options=[];bulk_only=[];ground_only=[]
sites=[]
def lattice(offset,axis):
    base=tuple(center)[axis]
    return sorted({base+650000*i+offset+d for i in range(-5,6) for d in (-50000,-25000,0,25000,50000)})
for x in (lattice(325000,0) if ball else range(39425000,45600001,650000) if rail else range(39325000,45600001,50000) if cells else range(39300000,45600001,50000)):
 for y in (lattice(325000,1) if ball else range(17725000,22500001,650000) if rail else range(17525000,22500001,50000) if cells else range(17500000,22500001,50000)):
    pos=x,y;distance=min(math.dist(pos,a) for a in seeds)
    if distance>2300000:continue
    v=barrel(b,pos,code);sh=v.GetEffectiveShape(p.F_Cu);hole=v.GetEffectiveHoleShape();bb=inflated_box(v,300000);hits=set()
    for q,geom,box in pads:
        if bb.Intersects(box) and sh.Collide(geom,100000):hits.add(tag(q))
    for o,h,box in holes:
        if bb.Intersects(box) and sh.Collide(h,252000):hits.add(tag(o))
    for o,g,box,l in shapes:
        if bb.Intersects(box) and (sh.Collide(g,202000) or hole.Collide(g,252000)):hits.add(tag(o))
    if any(z.Collide(sh,0) for z in zones):hits.add("rule-area")
    if rail:sites.append(dict(site_nm=pos,blocked_by=sorted(hits),nearest_conductor_mm=round(distance/1e6,3)))
    stats[len(hits)]+=1
    if len(hits)==1:singles[next(iter(hits))]+=1
    if hits=={"GND"}:
        blockers=[dict(uuid=o.m_Uuid.AsString(),layer=l,kind=o.GetClass()) for o,g,box,l in shapes if o.GetNetname()=="GND" and bb.Intersects(box) and (sh.Collide(g,202000) or hole.Collide(g,252000))]
        ground_only.append({"position_nm":pos,"hits":blockers})
    if hits and all(t.split(".")[0] in {"C1601","C1602","C1603","C1604","C1605","C1606","C1607","C1608"} for t in hits):
        bulk_only.append(dict(position_nm=pos,obstacles=sorted(hits)))
    if hits:continue
    best=None
    for a in sorted(seeds,key=lambda a:math.dist(a,pos)):
        dx,dy=x-a[0],y-a[1];diag=min(abs(dx),abs(dy));vx,vy=int(math.copysign(diag,dx)),int(math.copysign(diag,dy))
        for elbow in ((a[0]+vx,a[1]+vy),(x-vx,y-vy)):
            ts=[make(b,u,w,250000,code,p.F_Cu) for u,w in zip((a,elbow),(elbow,pos)) if u!=w]
            if any(inflated_box(t,260000).Intersects(box) and t.GetEffectiveShape(p.F_Cu).Collide(g,202000) for t in ts for o,g,box in front):continue
            if any(inflated_box(t,260000).Intersects(box) and t.GetEffectiveShape(p.F_Cu).Collide(g,252000) for t in ts for o,g,box in holes):continue
            best=dict(source_nm=a,elbow_nm=elbow,via_nm=pos,length_mm=sum(t.GetLength() for t in ts)/1e6);break
        if best:break
    if best:options.append(best)
out={"parent_sha256":cp["sha256"],"original_cpu_pins":[q.GetNumber() for q in lands],
     "sampled_by_obstacle_count":dict(stats),"single_blockers":dict(singles),"removable_cpu_bypasses_only":bulk_only,"ground_only":ground_only,"branch_options":options}
if rail:out["centers"]=sites
if ball:out["supply"]=anchor.GetNetname();out["anchor"]=ball
(root/("core-bank-supply-"+ball+".json" if ball else "cpu-second-power-barrel-centers.json" if rail else "soc-cpu-decoupler-pitch-centers.json" if cells else "soc-cpu-decoupler-ground-window.json" if lift else "soc-cpu-decoupler-drop.json")).write_text(json.dumps(out,indent=2)+"\n")
print(dict(stats),len(options),len(bulk_only),singles.most_common(6))
