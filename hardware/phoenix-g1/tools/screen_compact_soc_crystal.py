"""Find the admissible envelope for alternative crystal packages before selecting a replacement."""
from pathlib import Path
import hashlib
import json
import subprocess

import pcbnew as p

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
cp=json.loads((root/"layout-bga-referenced-barrel.json").read_text())
f=root/cp["board"];assert hashlib.sha256(f.read_bytes()).hexdigest()==cp["sha256"]
b=p.LoadBoard(str(f));soc=b.FindFootprintByReference("U1")
sinks=[tuple(soc.FindPadByNumber(pin).GetPosition()) for pin in ("AG25","AF25")]
sides={}
moving={"Y1","R1501","R1502","C1501","C1502"}
for side in (p.F_Cu,p.B_Cu):
    bounds=[]
    for part in b.GetFootprints():
        if part.GetReference() in moving or part.GetLayer()!=side:continue
        c=part.GetCourtyard(side)
        if not c.OutlineCount():continue
        for i in range(c.OutlineCount()):
            o=c.Outline(i);bounds.append([tuple(o.CPoint(j)) for j in range(o.PointCount())])
    sides[b.GetLayerName(side)]=bounds
analysis="""
import sys,json,math
from shapely.geometry import Polygon,box
from shapely.strtree import STRtree
d=json.load(sys.stdin)
results=[]
for side,polygons in d['sides'].items():
 idx=STRtree([Polygon(v) for v in polygons])
 for dims in [(4190,3490),(3100,2500),(2600,2200),(2200,1800)]:
    valid=[]
    for x in range(40500000,56500001,100000):
      for y in range(19000000,35100001,100000):
        radius=max(math.dist((x,y),s) for s in d['sinks'])
        if radius>8000000:continue
        for angle in (0,90):
            w,h=dims if angle==0 else dims[::-1]
            body=box(x-w*500-100000,y-h*500-100000,x+w*500+100000,y+h*500+100000)
            if not len(idx.query(body,predicate='intersects')):valid.append((radius,x,y,angle))
    results.append(dict(side=side,courtyard_mm=[n/1000 for n in dims],options=len(valid),closest=min(valid) if valid else None))
print(json.dumps(results))
"""
data=json.loads(subprocess.run(["python3","-c",analysis],input=json.dumps({"sides":sides,"sinks":sinks}),text=True,capture_output=True,check=True).stdout)
report={"board_sha256":cp["sha256"],"rows":data,"limits":"Courtyard-only geometry within 8 mm from both SoC balls, additional separation 0.10 mm. Does not include copper, package exits, passive bank, or electrical compatibility. Calculated candidate packages use indicative courtyard dimensions."}
(root/"soc-crystal-compact-envelope.json").write_text(json.dumps(report,indent=2)+"\n")
print([(r["side"],r["courtyard_mm"],r["options"]) for r in data])
