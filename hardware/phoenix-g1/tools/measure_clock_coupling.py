"""Measure copper spacing on each layer of the clock coupon, including terminal leads."""
from pathlib import Path
import hashlib
import json
import subprocess

import pcbnew

root = Path(__file__).resolve().parents[1] / "migration-rk3562/experiments/phy-power-parallel"
meta = json.loads((root / "ddr-clock-b-preserved-recovered.json").read_text())
pcb = root / meta["board"]
assert hashlib.sha256(pcb.read_bytes()).hexdigest() == meta["sha256"]
board = pcbnew.LoadBoard(str(pcb))
segments = {}
for trace in board.GetTracks():
    net = trace.GetNetname()
    if isinstance(trace, pcbnew.PCB_VIA) or net not in ("LPDDR4_CLKP_B", "LPDDR4_CLKN_B"):
        continue
    segments.setdefault(trace.GetLayerName(), {}).setdefault(net, []).append(
        [tuple(trace.GetStart()), tuple(trace.GetEnd()), trace.GetWidth()]
    )

code = """
import json,sys,math
from shapely.geometry import LineString
data=json.load(sys.stdin)
result=[]
for layer,nets in data.items():
 for net,segments in nets.items():
    others=[(LineString([a,b]),w) for other,parts in nets.items() if other!=net for a,b,w in parts]
    lengths=[0.,0.,0.]
    maximum=0.
    for a,b,w in segments:
        line=LineString([a,b])
        n=math.ceil(line.length/25000)
        for i in range(n):
            pt=line.interpolate((i+.5)/n,normalized=True)
            distance=min((line2.distance(pt)-(w+ow)/2 for line2,ow in others),default=math.inf)
            maximum=max(maximum,distance)
            group=0 if distance<=275000 else 1 if distance<=500000 else 2
            lengths[group]+=line.length/n/1e6
    result.append(dict(layer=layer,net=net,length_by_spacing_mm=lengths,maximum_edge_gap_mm=maximum/1e6 if math.isfinite(maximum) else None))
print(json.dumps(result))
"""
rows = json.loads(subprocess.run(["python3", "-c", code], input=json.dumps(segments), text=True, capture_output=True, check=True).stdout)
report = {"board_sha256": meta["sha256"], "samples_at_most_mm": .025, "edge_gap_bins_mm": ["<=0.275", "(0.275,0.5]", ">0.5"], "rows": rows, "scope": "Geometric nearest-edge distances only; no differential field, phase, package or via model."}
(root / "ddr-clock-b-preserved-coupling.json").write_text(json.dumps(report, indent=2)+"\n")
for row in rows:
    print(row["layer"], row["net"], [round(n,3) for n in row["length_by_spacing_mm"]])
