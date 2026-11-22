"""Look for a shared transfer within the reachable areas of A+ on F and In2, preserving clock A-."""
from pathlib import Path
import hashlib
import json
import math
import subprocess
import sys
import pcbnew as p
from phy_corridor_path import geometry

tools=Path(__file__).resolve().parent
root=tools.parent/"migration-rk3562/experiments/phy-power-parallel"
coupon=root/"runs/ddr-clock-a-split-copper-positive-ram-extended/phy-joint.kicad_pcb"
board=p.LoadBoard(str(coupon))
meta=json.loads((root/"ddr-clock-a-split-copper-positive-ram-extended.json").read_text())
attempt=max(meta["attempts"],key=lambda t:t["joined"])
net="LPDDR4_CLKP_A"
psections=[s for s in attempt["sections"] if s["phase"]==net]
source=psections[0]["origin"]
inner_tip=psections[2]["tip"]
old=psections[2]["origin"]
code=board.FindNet(net).GetNetCode()
trials=[]
options=json.loads((root/"ddr-clock-a-transition-sites.json").read_text())["pairs"]
other=next(s["origin"] for s in attempt["sections"] if s["phase"]=="LPDDR4_CLKN_A" and s["layer"]=="F.Cu" and s["origin"]!=[42500000,13350000])
sites={tuple(pos) for row in options if row["preserves_prior_fast_projections"] for pos,ground in zip(row["position_nm"],row["nearest_ground_barrel_mm"]) if ground<=1 and 650000<=math.dist(pos,other)<=1200000}
unreserved = "--without-negative-launch" in sys.argv
baseline=json.loads((root/"ddr-clock-b-preserved-recovered.json").read_text())
reference_board=p.LoadBoard(str(root/baseline["board"])) if unreserved else board
fronts=[]
for lid,anchor in ((p.F_Cu,source),(p.In2_Cu,inner_tip)):
    req=json.loads(Path("/tmp/phoenix-clock-a-"+board.GetLayerName(lid)+".json").read_text())
    inputs=dict(via_nm=[anchor,old],plane=req["plane"],geometry=[*geometry(reference_board,lid,code,oval_caps=True),req["geometry"][2]],collect_frontier=True,reference_half_width_nm=200000,max_path_nm=9000000)
    output=subprocess.run(["python3",str(tools/"ddr_plane_grid.py")],input=json.dumps(inputs),text=True,capture_output=True,check=True)
    front={tuple(row[0]) for row in json.loads(output.stdout)["frontier"]}
    fronts.append(front)
for site in sorted(sites):
    distances=[min((math.dist(pt,site) for pt in front),default=math.inf) for front in fronts]
    if max(distances)>160000:continue
    trials.append({"site":site,"nearest_front_mm":[v/1e6 for v in distances]})
common = fronts[0] & fronts[1]
closest = min(((math.dist(a,b),a,b) for a in fronts[0] for b in fronts[1]),key=lambda x:x[0])
report={"shared_grid_points":len(common),"minimum_front_distance_mm":closest[0]/1e6,"closest_points_nm":closest[1:],"board_sha256":hashlib.sha256(coupon.read_bytes()).hexdigest(),"negative_barrel_nm":other,"filtered_sites":len(sites),"front_sizes":[len(f) for f in fronts],"potential_joins":trials}
(root/("ddr-clock-a-positive-barrel-unreserved.json" if unreserved else "ddr-clock-a-positive-barrel-shift.json")).write_text(json.dumps(report,indent=2)+"\n")
print(len(sites),[len(f) for f in fronts],len(trials))
