"""Search for paired signal/GND barrel placements near the shortest exterior package escapes."""
from pathlib import Path
import hashlib
import json
import math
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import barrel,make

r=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
read=lambda n:json.loads((r/(n+".json")).read_text())
cp=read("layout-bga-referenced-barrel");layout=read("bga-joint-return-sites")
src=r/cp["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest()==layout["parent_sha256"]
b=p.LoadBoard(str(src));b.BuildConnectivity()
gcode=b.FindNet("GND").GetNetCode()
layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
planes=[next(z.GetFilledPolysList(l) for z in b.Zones() if z.GetNetname()=="GND" and z.HasFilledPolysForLayer(l)) for l in (p.In1_Cu,p.In4_Cu)]
zones=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
all_nodes=list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]
landmap={t["pad"]:t for t in read("ddr-referenced-escape-land-proximity")["rows"]}
rows=[]
for trial in layout["trials"]:
    options=trial.get("joined_options",[])
    if not options:continue
    row=landmap[trial["pad"]]
    origin=options[0]["tip_nm"]
    near=[o for o in all_nodes if o.m_Uuid.AsString()!=row["uuid"] and inflated_box(o,4000000).Contains(p.VECTOR2I(*origin))]
    shapes=[(o.GetEffectiveShape(l),o.GetBoundingBox()) for o in near if o.GetNetCode()!=gcode for l in layers if o.IsOnLayer(l)]
    lands=[q.GetEffectiveShape(q.GetParentFootprint().GetLayer()) for q in near if isinstance(q,p.PAD)]
    holes=[q.GetEffectiveHoleShape() for q in near if isinstance(q,p.PCB_VIA) or isinstance(q,p.PAD) and q.GetDrillSize().x]
    cache={};compatible=[]
    for step in options:
        signal=step["via_nm"]
        scode=b.FindNet(row["net"]).GetNetCode()
        sig=barrel(b,signal,scode)
        path=[make(b,a,z,200000,scode,p.F_Cu) for a,z in zip([step["tip_nm"],step["elbow_nm"]],[step["elbow_nm"],signal]) if tuple(a)!=tuple(z)]
        for dx in range(-20,21):
            for dy in range(-20,21):
                length=math.hypot(dx,dy)*50000
                if not 650000<=length<=1000000:continue
                pt=signal[0]+dx*50000,signal[1]+dy*50000
                if pt not in cache:
                    via=barrel(b,pt,gcode);sh=via.GetEffectiveShape(p.F_Cu);hole=via.GetEffectiveHoleShape();bb=inflated_box(via,300000)
                    cache[pt]=not (any(sh.Collide(land,100000) for land in lands)
                        or any(sh.Collide(h,252000) for h in holes)
                        or any(bb.Intersects(box) and (sh.Collide(geo,202000) or hole.Collide(geo,252000)) for geo,box in shapes)
                        or any(z.Collide(sh,0) for z in zones))
                    if cache[pt]:
                        rim=[p.VECTOR2I(round(pt[0]+280000*math.cos(k*math.tau/16)),round(pt[1]+280000*math.sin(k*math.tau/16))) for k in range(16)]
                        cache[pt]=all(z.Contains(t) for t in rim for z in planes)
                if not cache[pt]:continue
                g=barrel(b,pt,gcode)
                if any(g.GetEffectiveShape(p.F_Cu).Collide(t.GetEffectiveShape(p.F_Cu),202000) for t in [sig]+path):continue
                compatible.append({"signal":step,"ground":pt,"distance_mm":length/1e6})
    rows.append({"pad":row["pad"],"signal_options":len(options),"ground_locations_examined":len(cache),"feasible":compatible})
(r/"bga-joint-ground-solutions.json").write_text(json.dumps({"parent_sha256":cp["sha256"],"rows":rows},indent=2)+"\n")
print([(t["pad"],len(t["feasible"])) for t in rows])
