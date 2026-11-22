"""Screen two ordinary through vias at A clock ideal transition locations, with stubs through all layers."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import pcbnew as p

root = Path(__file__).resolve().parents[1] / "migration-rk3562/experiments/phy-power-parallel"
meta = json.loads((root / "ddr-clock-b-preserved-recovered.json").read_text())
source = root / meta["board"]
request = json.loads(Path(sys.argv[1]).read_text())
assert hashlib.sha256(source.read_bytes()).hexdigest() == meta["sha256"] == request["sha256"]
board = p.LoadBoard(str(source))
tracks = list(board.GetTracks())
request["traces"] = [
    [tuple(t.GetStart()), tuple(t.GetEnd()), t.GetWidth() if not isinstance(t,p.PCB_VIA) else t.GetWidth(p.F_Cu)]
    for t in tracks
]
fast_prefixes = ("LPDDR4_", "USB_", "MUX_", "SOC_USB_", "ADDON_USB_", "EMMC_", "SOC_EMMC_", "ETH_", "PHY_", "WIFI_")
request["fast"] = [[tuple(t.GetStart()), tuple(t.GetEnd()), t.GetWidth()] for t in tracks
    if not isinstance(t,p.PCB_VIA) and t.GetNetname().startswith(fast_prefixes)]
request["ground"] = [tuple(t.GetPosition()) for t in tracks if isinstance(t,p.PCB_VIA) and t.GetNetname()=="GND"]
request["pads"] = []
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if not any(pad.IsOnLayer(l) for l in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)):
            continue
        bb = pad.GetBoundingBox()
        request["pads"].append([bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom()])
request["keepouts"] = []
for zone in list(board.Zones()) + [z for f in board.GetFootprints() for z in f.Zones()]:
    if zone.GetIsRuleArea():
        if zone.GetDoNotAllowVias():
            for i in range(zone.Outline().OutlineCount()):
                line = zone.Outline().Outline(i)
                request["keepouts"].append([tuple(line.CPoint(k)) for k in range(line.PointCount())])

analysis = """
import json,sys,math
import shapely
from shapely.geometry import Point,LineString,box,Polygon
from shapely.strtree import STRtree
d=json.load(sys.stdin)
blocked=[]
for a,b,w in d["traces"]:
    shape=Point(a) if a==b else LineString([a,b])
    blocked.append(shape.buffer(w/2+427000,quad_segs=12))
for bounds in d["pads"]:
    blocked.append(box(*bounds).buffer(427000))
for ring in d["keepouts"]:blocked.append(Polygon(ring).buffer(225000))
index=STRtree(blocked)
projected=STRtree([LineString([a,b]).buffer(w/2+630000) for a,b,w in d["fast"]])
grounds=STRtree([Point(pt) for pt in d["ground"]])
sites={}
for center in d["centers"]:
    for angle in (0,45,90,135):
        x,y=center
        u=round(350000*math.cos(math.radians(angle)));v=round(350000*math.sin(math.radians(angle)))
        pair=[(x+u,y+v),(x-u,y-v)]
        clear=True
        for pos in pair:
            if pos not in sites:
                sites[pos]=len(index.query(Point(pos),predicate="intersects"))==0
            clear &= sites[pos]
        if clear:
            near_ground=[float(grounds.query_nearest(Point(pos),return_distance=True)[1][0])/1e6 for pos in pair]
            intact=all(len(projected.query(Point(pos),predicate="intersects"))==0 for pos in pair)
            print(json.dumps({"center":center,"position_nm":pair,"preserves_prior_fast_projections":intact,"nearest_ground_barrel_mm":near_ground}))
"""
raw = subprocess.run(["python3", "-c", analysis], input=json.dumps(request), text=True, capture_output=True, check=True)
options = [json.loads(line) for line in raw.stdout.splitlines()]
report = {"sha256":meta["sha256"], "centers_examined":len(request["centers"]),"orientations_per_center":4,"feasible_pair_count":len(options),"pairs":options,"basis":"0.45/0.20 mm through via, 0.70 mm pitch, 0.202 mm copper clearance. Pad bounding boxes are conservative. Existing drill and reference-plane impact, launch continuity and reference returns require native checks."}
(root/"ddr-clock-a-transition-sites.json").write_text(json.dumps(report,indent=2)+"\n")
print(len(options),sum(o["preserves_prior_fast_projections"] for o in options),sum(o["preserves_prior_fast_projections"] and max(o["nearest_ground_barrel_mm"])<=1 for o in options))
