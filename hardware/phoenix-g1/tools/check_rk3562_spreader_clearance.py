"""Measure candidate lid contact and spreader footprints against actual front-side courtyards."""
import hashlib
import json
import math
from pathlib import Path

import pcbnew

root = Path(__file__).resolve().parents[1]
work = root / "migration-rk3562/experiments/phy-power-parallel"
checkpoint = json.loads((work / "layout-pmic-image-c468.json").read_text())
source = work / checkpoint["board"]
assert hashlib.sha256(source.read_bytes()).hexdigest() == checkpoint["sha256"]
board = pcbnew.LoadBoard(str(source))
processor = board.FindFootprintByReference("U1")
center = processor.GetPosition()
assert not processor.IsFlipped()
rectangles = []
without_courtyard = set()
for side in (10, 12, 13.9, 16, 20, 24):
    half = round(side * 500000)
    shape = pcbnew.SHAPE_RECT(center.x-half, center.y-half, 2*half, 2*half)
    collisions = []
    for fp in board.GetFootprints():
        if fp.GetLayer() != pcbnew.F_Cu or fp.GetReference() == "U1":
            continue
        court = fp.GetCourtyard(pcbnew.F_Cu)
        if court.OutlineCount() == 0:
            without_courtyard.add(fp.GetReference())
            continue
        if court.Collide(shape, 0):
            collisions.append(fp.GetReference())
    rectangles.append({"square_mm": side, "intersecting_front_courtyards": sorted(collisions)})
mounts = {}
for fp in board.GetFootprints():
    if fp.GetReference().startswith("H810"):
        mounting_pad, = list(fp.Pads())
        assert mounting_pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
        xy = mounting_pad.GetPosition()
        mounts[fp.GetReference()] = {"position_mm": [xy.x/1e6, xy.y/1e6], "center_distance_mm": round(math.dist(tuple(center),tuple(xy))/1e6,3)}
# Only the three auxiliary holes may be used; H8101/2 remain reserved for the accessory.
triangle = [mounts[ref]["position_mm"] for ref in ("H8103", "H8104", "H8105")]
def signed_double_area(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
orientation = math.copysign(1, signed_double_area(*triangle))
def support_margin(point):
    return min(orientation*signed_double_area(a,b,point)/math.dist(a,b)
               for a,b in zip(triangle, triangle[1:] + triangle[:1]))
x, y = center.x/1e6, center.y/1e6
support = {"mounts": ["H8103","H8104","H8105"], "soc_center_signed_margin_mm": round(support_margin((x,y)),3),
           "12mm_contact_corner_min_signed_margin_mm": round(min(support_margin((x+dx,y+dy)) for dx in (-6,6) for dy in (-6,6)),3),
           "interpretation": "Positive is inside all three support edges. Margins assess static placement only; fastener stiffness, impact and maximum preload are unknown."}
result = {"parent_sha256": checkpoint["sha256"], "front_side_soc_center_mm": [center.x/1e6, center.y/1e6],
          "package_nominal_side_mm": 13.9, "projected_front_courtyards": rectangles, "mounts": mounts, "auxiliary_support_triangle": support,
          "front_footprints_without_courtyard": sorted(without_courtyard),
          "limits": "Plan view. Display, flex, clamp preload, TIM compression and enclosure heights remain unverified. A metal plate can overhang a courtyard only after a Z-clearance check."}
(work/"rk3562-spreader-xy.json").write_text(json.dumps(result,indent=2)+"\n")
print([(row["square_mm"],len(row["intersecting_front_courtyards"])) for row in rectangles])
