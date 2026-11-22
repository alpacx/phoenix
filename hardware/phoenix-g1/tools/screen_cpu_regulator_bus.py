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
for net in ("I2C0_SCL","I2C0_SDA"):
    ends=[next(q for q in b.FindFootprintByReference(ref).Pads() if q.GetNetname()==net) for ref in ("U1","U10")]
    pos=[tuple(q.GetPosition()) for q in ends]
    data={"via_nm":pos,"plane":plane,"geometry":[*geometry(b,layer,ends[0].GetNetCode(),oval_caps=True),keepouts],"reference_half_width_nm":200000,"max_path_nm":26000000,"compact_45":True}
    solution=json.loads(subprocess.run(["python3",str(tools/"ddr_plane_grid.py")],input=json.dumps(data),text=True,capture_output=True,check=True).stdout)
    rows.append({"net":net,"pads":[ref+"."+q.GetNumber() for ref,q in zip(("U1","U10"),ends)],"route":solution})
    (Path("/tmp")/("phoenix-regulator-"+net+".json")).write_text(json.dumps(data))
(r/"cpu-regulator-i2c-front.json").write_text(json.dumps({"board_sha256":cp["sha256"],"rows":rows},indent=2)+"\n")
print(rows)
