"""Screen direct F.Cu routes between the RK3562 boot I2C pads and the RK860 controller."""
from pathlib import Path
import hashlib
import json
import subprocess
import pcbnew as p
from phy_corridor_path import geometry

tools=Path(__file__).resolve().parent
r=tools.parent/"migration-rk3562/experiments/phy-power-parallel"
cp=json.loads((r/"layout-command-ca1.json").read_text())
src=r/cp["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp["sha256"]
b=p.LoadBoard(str(src))
layer=p.F_Cu
ground=next(z.GetFilledPolysList(p.In1_Cu) for z in b.Zones() if z.GetNetname()=="GND" and z.HasFilledPolysForLayer(p.In1_Cu))
def pts(loop):return [tuple(loop.CPoint(i)) for i in range(loop.PointCount())]
plane=[[pts(ground.Outline(i)),[pts(ground.Hole(i,j)) for j in range(ground.HoleCount(i))]] for i in range(ground.OutlineCount())]
keepouts=[pts(z.Outline().Outline(i)) for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(layer) for i in range(z.Outline().OutlineCount())]
rows=[]
import sys
soc = "--pmu-bypass" in sys.argv
layer = p.B_Cu if soc else p.F_Cu
if soc:
    ground=next(z.GetFilledPolysList(p.In4_Cu) for z in b.Zones() if z.GetNetname()=="GND" and z.HasFilledPolysForLayer(p.In4_Cu))
    plane=[[pts(ground.Outline(i)),[pts(ground.Hole(i,j)) for j in range(ground.HoleCount(i))]] for i in range(ground.OutlineCount())]
    keepouts=[pts(z.Outline().Outline(i)) for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(layer) for i in range(z.Outline().OutlineCount())]

q=b.FindFootprintByReference("C1625" if soc else "R2011").FindPadByNumber("1" if soc else "2")
b.BuildConnectivity()
g=b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference("TP5" if soc else "C2007").FindPadByNumber("1"))
seeds=set()
at=tuple(q.GetPosition())
import math
for o in g:
    if not o.IsOnLayer(layer):continue
    if isinstance(o,p.PAD):seeds.add(tuple(o.GetPosition()))
    elif isinstance(o,p.PCB_TRACK):
        a,z=tuple(o.GetStart()),tuple(o.GetEnd())
        if min(math.dist(a,at),math.dist(z,at))>12000000:continue
        for i in range(5):seeds.add(tuple(round(u+(v-u)*i/4) for u,v in zip(a,z)))
near=sorted((x for x in seeds if math.dist(x,at)<=8000000),key=lambda x:math.dist(x,at))
req={"plane":plane,"geometry":[*geometry(b,layer,q.GetNetCode(),oval_caps=True),keepouts],"reference_half_width_nm":200000,"max_path_nm":12000000,"compact_45":True}
payload=dict(req,via_nm=[at,near[0]],collect_frontier=True)
front=json.loads(subprocess.run(["python3",str(tools/"ddr_plane_grid.py")],input=json.dumps(payload),text=True,capture_output=True,check=True).stdout)
nodes=[x[0] for x in front.get("frontier",[])]
goals=sorted((x for x in near if any(math.dist(x,n)<150000 for n in nodes)),key=lambda pt:math.dist(pt,at))
for goal in goals:
    result=json.loads(subprocess.run(["python3",str(tools/"ddr_plane_grid.py")],input=json.dumps(dict(req,via_nm=[at,goal])),text=True,capture_output=True,check=True).stdout)
    if "path" in result:
        rows.append({"goal":goal,"result":result});break
report={"board_sha256":cp["sha256"],"seeds":len(near),"front_nodes":len(nodes),"goals":len(goals),"rows":rows}
(r/("soc-pmu-bypass-frontier.json" if soc else "wifi-d1-existing-bias-front.json")).write_text(json.dumps(report,indent=2)+"\n")
print(report)
