"""Measure via-to-originating-ball land overlap on the actual native DDR escape geometry."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import sys
import pcbnew as p

r=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
read=lambda n:json.loads((r/(n+".json")).read_text())
current="--referenced" in sys.argv
cp=read("layout-bga-referenced-barrel" if current else "layout-command-ca1");src=r/cp["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp["sha256"]
b=p.LoadBoard(str(src));b.BuildConnectivity()
release=read("ddr-clock-open-escape-release");refit=read("ddr-clock-b-recovered")
removed={v["uuid"] for v in release["released"]};recovered=set(refit["original_vias_recovered"])
allpads={q.m_Uuid.AsString():q for f in b.GetFootprints() for q in f.Pads() if f.GetReference() in ("U1","U2")}
rows=[]
for via in b.GetTracks():
    if not isinstance(via,p.PCB_VIA) or via.m_Uuid.AsString() not in removed:continue
    ids={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(via)}
    pad,=[allpads[k] for k in ids & allpads.keys()]
    land=pad.GetEffectiveShape(p.F_Cu)
    rows.append({"uuid":via.m_Uuid.AsString(),"pad":pad.GetParentFootprint().GetReference()+"."+pad.GetNumber(),"net":via.GetNetname(),
                 "center_to_center_mm":(via.GetPosition()-pad.GetPosition()).EuclideanNorm()/1e6,
                 "metal_overlaps_land":land.Collide(via.GetEffectiveShape(p.F_Cu),0),
                 "drill_intersects_land":land.Collide(via.GetEffectiveHoleShape(),0),
                 "via_fill_setting":via.GetFillingMode(),"via_cap_setting":via.GetCappingMode(),
                 "drill_mm":via.GetDrillValue()/1e6,"via_dia_mm":via.GetWidth(p.F_Cu)/1e6,"pad_copper_mm":[x/1e6 for x in pad.GetSize()],
                 "restored_in_clock_coupon":via.m_Uuid.AsString() in recovered})
counts={group:dict(total=len(items),metal_overlaps=sum(q["metal_overlaps_land"] for q in items),drill_intersects=sum(q["drill_intersects_land"] for q in items)) for group,items in [("all_released",rows),("recovered",[q for q in rows if q["restored_in_clock_coupon"]]),("displaced",[q for q in rows if not q["restored_in_clock_coupon"]])]}
(r/("ddr-referenced-escape-land-proximity.json" if current else "ddr-escape-land-proximity.json")).write_text(json.dumps({"board_sha256":cp["sha256"],"counts":counts,"rows":rows,"limits":"Nominal copper pad and nominal drilled geometry. Actual drill registration, solder mask aperture, filling/capping and solder-process yield need manufacturer verification."},indent=2)+"\n")
print(counts,Counter((t["via_fill_setting"],t["via_cap_setting"]) for t in rows if t["drill_intersects_land"]))
