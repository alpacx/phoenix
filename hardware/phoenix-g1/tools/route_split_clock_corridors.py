"""Join the A clock coarse corridors through a common candidate barrel pair with a nearby return."""
from pathlib import Path
import json
import math
import sys

from lpddr_clock_corridor_grid import run

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
candidates=json.loads((root/"ddr-clock-a-transition-sites.json").read_text())
requests=[json.loads(Path("/tmp/phoenix-clock-a-"+layer+".json").read_text()) for layer in ("F.Cu","In2.Cu")]
source,dest=requests[0]["centers"]
sites=[s for s in candidates["pairs"] if s["preserves_prior_fast_projections"] and max(s["nearest_ground_barrel_mm"])<=1.]
def score(site):
    return sum(math.dist(site["center"],p) for p in (source,dest))
sites.sort(key=score)
ram_gate = "--ram-gate" in sys.argv
positive_gate = "--positive-ram" in sys.argv
if positive_gate:
    dest = [dest[0]-400000,dest[1]]
suffix = "-positive-ram" if positive_gate else "-ram-gate" if ram_gate else ""
attempts=[]
for site in sites:
    xy=site["center"]
    if any(xy==t["center"] for t in attempts):continue
    legs=[]
    for req,gates,radii in zip(requests,([source,xy],[xy,dest]),([1500000,1],[1,750000 if ram_gate else 1500000])):
        legs.append(run(dict(req,centers=gates,gate_radii_nm=radii,route=True))["middle"])
    attempts.append(dict(center=xy,site=site,legs=legs))
    if all(legs) or ram_gate or positive_gate:break
report={"board_sha256":candidates["sha256"],"attempts":attempts,"whole_pair_qualified":False}
(root/("ddr-clock-a-split-trunks"+suffix+".json")).write_text(json.dumps(report,indent=2)+"\n")
print(len(attempts),[leg["length_mm"] if leg else None for leg in attempts[-1]["legs"]])
