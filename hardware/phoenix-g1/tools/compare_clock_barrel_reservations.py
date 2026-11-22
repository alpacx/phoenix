"""Preserve displaced barrel antipads individually and compare B-clock corridors."""
import json
import sys
from pathlib import Path

from shapely.geometry import LineString, Point
from lpddr_clock_corridor_grid import run

root = Path(__file__).resolve().parents[1] / "migration-rk3562/experiments/phy-power-parallel"
with open(sys.argv[1]) as stream:
    request = json.load(stream)
baseline = json.loads((root / "ddr-clock-b-recovered.json").read_text())
locations = [Point(point) for point in request["released_nm"]]
trials = []
for site in baseline["still_requiring_relocation"]:
    pos = site["location_nm"]
    metal, pads, exclusions = request["geometry"]
    # Use the original antipad as an obstacle, including return margin.
    # 0.86 mm represents the plane void diameter before pair clearance.
    geometry = [metal + [[pos, pos, 860000]], pads, exclusions]
    result = run(dict(request, geometry=geometry))
    middle = result["middle"]
    if middle:
        path = LineString(middle["points_nm"])
        nearby = sum(path.distance(point) < 855000 for point in locations)
        assert path.distance(Point(pos)) > 855000
    else:
        nearby = None
    trials.append(dict(uuid=site["uuid"], nearby_barrels=nearby, middle=middle))
out = {"baseline_sha256":baseline["baseline_sha256"], "trials":trials}
(root / "ddr-clock-b-barrel-reservations.json").write_text(json.dumps(out, indent=2)+"\n")
print([t["nearby_barrels"] for t in trials])
