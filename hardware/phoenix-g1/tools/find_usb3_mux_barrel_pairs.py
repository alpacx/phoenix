"""Find joint conventional-via transitions for both SuperSpeed transmitter pairs at the mux."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make, barrel

root = Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
base = json.loads((root/"layout-emmc-data-power.json").read_text()); source=root/base["board"]
assert hashlib.sha256(source.read_bytes()).hexdigest()==base["sha256"]
b=p.LoadBoard(str(source));mux=b.FindFootprintByReference("U6")
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
near=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if inflated_box(o,6500000).Contains(mux.GetPosition())]
shapes={l:[(o.GetNetCode(),o.GetEffectiveShape(l),o.GetBoundingBox(),o) for o in near if o.IsOnLayer(l)] for l in layers}
holes=[(o.GetEffectiveHoleShape(),o.GetBoundingBox()) for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
restrictions=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
ground=[o for o in near if isinstance(o,p.PCB_VIA) and o.GetNetname()=="GND"]
def copper_hits(obj,layer):
    geom=obj.GetEffectiveShape(layer);bb=inflated_box(obj,260000)
    return [o for code,s,box,o in shapes[layer] if code!=obj.GetNetCode() and bb.Intersects(box) and geom.Collide(s,200000)]
def identity(o):
    return o.GetParentFootprint().GetReference()+"."+o.GetNumber() if isinstance(o,p.PAD) else o.GetNetname()
rows=[]
for numbers in (("17","16"),("21","20")):
    by_pin=[]
    for n in numbers:
        pin=mux.FindPadByNumber(n);sx=pin.GetPosition().x;sy=pin.GetBoundingBox().GetTop()+25000;net=pin.GetNetCode()
        valid=[];counts=Counter();stops=Counter()
        for dx in range(-1200000,1200001,50000):
            for dy in range(350000,2050001,50000):
                if abs(dx)>dy:continue
                at=(sx+dx,sy-dy);v=barrel(b,at,net);metal=v.GetEffectiveShape(p.F_Cu);drill=v.GetEffectiveHoleShape();bb=inflated_box(v,350000)
                if metal.Collide(pin.GetEffectiveShape(p.F_Cu),75000):continue
                if any(shape.Collide(metal,0) for shape in restrictions):continue
                hits={identity(o) for l in layers for o in copper_hits(v,l)}
                if hits:
                    if len(hits)==1:stops.update(hits)
                    continue
                counts["barrel_copper_clear"]+=1
                if any(bb.Intersects(box) and drill.Collide(h,252000) for h,box in holes):continue
                if any(bb.Intersects(box) and code!=net and drill.Collide(s,252000) for l in layers for code,s,box,o in shapes[l]):continue
                counts["drill_clear"]+=1
                for elbow in ((sx,at[1]+abs(dx)),(at[0],sy-abs(dx))):
                    pts=[(sx,sy),elbow,at];lead=[make(b,a,c,200000,net,p.F_Cu) for a,c in zip(pts,pts[1:]) if a!=c]
                    if any(copper_hits(t,p.F_Cu) for t in lead):continue
                    nearest=min((math.dist(at,tuple(o.GetPosition())) for o in ground),default=float("inf"))
                    valid.append((at,lead,v,nearest));break
        by_pin.append(valid)
        rows.append({"pin":n,"stages":dict(counts),"reachable_sites":len(valid),"single_barrel_blockers":stops.most_common(8)})
    options=[]; pair_counts=Counter(); spacing_range=[]; achievable=[]
    for a,ap,av,ag in by_pin[0]:
        for c,cp,cv,cg in by_pin[1]:
            spacing=math.dist(a,c)
            spacing_range.append(spacing/1e6)
            if spacing>1100000 or spacing<652000:continue
            pair_counts["barrel_spacing"]+=1
            if any(t.GetEffectiveShape(p.F_Cu).Collide(o.GetEffectiveShape(p.F_Cu),200000) for t in [*ap,av] for o in [*cp,cv]):continue
            pair_counts["mutual_copper"]+=1
            skew=abs(sum(t.GetLength() for t in ap)-sum(t.GetLength() for t in cp))
            achievable.append((round(skew/1000,2),round(max(ag,cg)/1e6,3)))
            if skew<=150000 and max(ag,cg)<=1000000:
                options.append({"sites_nm":[a,c],"length_delta_um":round(skew/1000,2),"ground_barrel_max_mm":round(max(ag,cg)/1e6,4)})
    rows.append({"pair":numbers,"simultaneous_options":options,"constraints":dict(pair_counts),"spacing_min_max_mm":([min(spacing_range),max(spacing_range)] if spacing_range else []),"skew_um_ground_mm":sorted(set(achievable))})
result={"parent_sha256":base["sha256"],"rows":rows,"adopted":False,"scope":"0.45/0.20 mm through vias outside terminals, first 2.05 mm from the mux; two lead orders, both conductors, no changes to existing copper. Coupled stack, return barrel plane membership, native DRC and residual path to AC capacitors need separate validation."}
(root/"usb3-mux-barrel-pair-window.json").write_text(json.dumps(result,indent=2)+"\n")
print([(r.get("pin",r.get("pair")),r.get("reachable_sites",len(r.get("simultaneous_options",[])))) for r in rows])
