"""Measure candidate lid contact and spreader footprints against actual front-side courtyards."""
import hashlib
import json
import math
from pathlib import Path

import pcbnew

root = Path(__file__).resolve().parents[1]
work = root / "migration-rk3562/experiments/phy-power-parallel"
checkpoint = json.loads((work / "layout-debug-rx-front-probe.json").read_text())
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
# Manufacturer body dimensions at the seating plane. XY is checked against the
# footprint fabrication rectangle before using the maximum body envelope.
bodies = {
    "U2": ((10.0, 15.0), (10.1, 15.1), 1.0, "migration-rk3562/experiments/lpddr4-1gb/H9HCNNN8KUMLHR.pdf p. 7"),
    "FB2001": ((2.0, 1.25), (2.2, 1.45), 1.05, "reference/wifi-ferrite-c15957.pdf, Shape & Dimensions"),
    "Y2001": ((5.0, 3.2), (5.2, 3.4), 1.30, "reference/wifi-clock-c5274152.pdf p. 1, OV side view"),
    "C2204": ((2.0, 1.25), (2.2, 1.45), 0.95, "migration-rk3562/experiments/boot-component-review-parallel/sources/CL21A226MOCLRN-product.html, L/W/T Size"),
}
overlaps = {}
for ref, (nominal, maximum, height, document) in bodies.items():
    fp = board.FindFootprintByReference(ref)
    # These four footprints currently use zero rotation and body-centred origins.
    assert not fp.IsFlipped() and abs(fp.GetOrientationDegrees()) < 1e-6
    fab, = [item for item in fp.GraphicalItems() if isinstance(item, pcbnew.PCB_SHAPE)
            and item.GetLayer() == pcbnew.F_Fab and item.GetShape() == pcbnew.SHAPE_T_RECT]
    a, b = fab.GetStart(), fab.GetEnd()
    assert a + b == fp.GetPosition() + fp.GetPosition()
    assert (abs(b.x-a.x), abs(b.y-a.y)) == tuple(round(v*1e6) for v in nominal)
    fx, fy = fp.GetPosition().x/1e6, fp.GetPosition().y/1e6
    size = 16.0
    dx = min(x+size/2, fx+maximum[0]/2) - max(x-size/2, fx-maximum[0]/2)
    dy = min(y+size/2, fy+maximum[1]/2) - max(y-size/2, fy-maximum[1]/2)
    overlaps[ref] = {"source": document, "maximum_body_mm": [*maximum, height],
                     "projected_overlap_with_16mm_plate_mm": [round(max(dx,0),3),round(max(dy,0),3)],
                     "height_above_minimum_soc_mm": round(height-0.795,3)}
result["seating_plane_dimensions"] = {
    "soc_source": "reference/rk3562-datasheet-v2.1.pdf p. 17, figures 2-4 and 2-5",
    "soc_height_min_nom_max_mm": [0.795, 0.870, 0.947],
    "soc_body_xy_min_nom_max_mm": [13.80, 13.90, 14.00],
    "package_height_span_mm": 0.152,
    "12mm_square_centered_contact_to_minimum_package_edge_mm": 0.90,
    "16mm_plate_overlapping_bodies": overlaps,
    "courtyards_with_unverified_body_heights": sorted(set(rectangles[3]["intersecting_front_courtyards"])-set(bodies)),
    "scope": "Analysis uses drawing heights on a common seating plane. Reflow, tilt, PCB warp, case and fastener tolerances, TIM thickness after compression and acceptable package pressure still require a full assembly tolerance stack. XY contact projection does not establish permissible contact area or thermal resistance."
}
(work/"rk3562-spreader-xy.json").write_text(json.dumps(result,indent=2)+"\n")
print([(row["square_mm"],len(row["intersecting_front_courtyards"])) for row in rectangles])
