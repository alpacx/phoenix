"""Screen F.Cu CPU launch and quantify copper loss of the installed HF branch."""
import hashlib
import json
import math
import subprocess
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry

tools = Path(__file__).resolve().parent
root = tools.parent / "migration-rk3562/experiments/phy-power-parallel"
state = json.loads((root/"layout-cpu-local-hf-bypass.json").read_text())
src = root/state["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest() == state["sha256"]
board = p.LoadBoard(str(src))
board.BuildConnectivity()
soc = board.FindFootprintByReference("U1")
coil = board.FindFootprintByReference("L1001").FindPadByNumber("2")
balls = [q for q in soc.Pads() if q.GetNetCode() == coil.GetNetCode()]
assert len(balls) == 6
launch = [tuple(q.GetPosition()) for q in balls]
target = tuple(coil.GetPosition())
# Check whether the power corridor can exit the package, in any direction.
cx,cy = map(round,map(lambda v:sum(v)/len(v),zip(*launch)))
edge = [(cx+dx,cy+dy) for dx in range(-3000000,3000001,250000) for dy in range(-3000000,3000001,250000) if max(abs(dx),abs(dy))==3000000]
sources=set(launch)
load_ids={item.m_Uuid.AsString() for item in board.GetConnectivity().GetConnectedItems(balls[0])}
for track in board.GetTracks():
    if track.m_Uuid.AsString() not in load_ids:continue
    if isinstance(track,p.PCB_TRACK) and not isinstance(track,p.PCB_VIA) and track.GetLayer()==p.F_Cu:
        a,z=tuple(track.GetStart()),tuple(track.GetEnd())
        steps=max(1,math.ceil(track.GetLength()/50000))
        sources.update(tuple(round(u+(v-u)*j/steps) for u,v in zip(a,z)) for j in range(steps+1))
rows=[]
for width in (600000,800000):
    req=dict(geometry=geometry(board,p.F_Cu,coil.GetNetCode(),oval_caps=True),
             width=width,sites=sorted(sources),target=edge,limit=6500000)
    proc=subprocess.run(["python3",str(tools/"screen_cpu_launch_corridor.py")],input=json.dumps(req),text=True,capture_output=True,check=True)
    result=json.loads(proc.stdout)
    rows.append(dict(width_mm=width/1e6,reachable_grid_vertices=result["front_nodes"],path_nm=result["path"],closest_nm=result["closest"]))
via=next(v for v in board.GetTracks() if isinstance(v,p.PCB_VIA) and tuple(v.GetPosition())==(42025000,20325000))
thickness=board.GetDesignSettings().GetBoardThickness()/1e6
source_copper=board.GetConnectivity().GetConnectedItems(coil)
source_ids={item.m_Uuid.AsString() for item in source_copper}
all_output_vias=[tuple(v.GetPosition()) for v in board.GetTracks() if isinstance(v,p.PCB_VIA) and v.m_Uuid.AsString() in source_ids]
kelvin={(63900000,18500000),(56500000,28500000)}
assert kelvin.issubset(all_output_vias)
source_vias=[xy for xy in all_output_vias if xy not in kelvin]
inner_access=[]
for layer in (p.In2_Cu,p.In3_Cu):
    for width in (600000,800000):
        req=dict(geometry=geometry(board,layer,coil.GetNetCode()),width=width,
                 sites=[tuple(via.GetPosition())],target=edge,limit=6500000)
        proc=subprocess.run(["python3",str(tools/"screen_cpu_launch_corridor.py")],input=json.dumps(req),text=True,capture_output=True,check=True)
        result=json.loads(proc.stdout)
        inner_access.append(dict(layer=board.GetLayerName(layer),width_mm=width/1e6,
            reachable_grid_vertices=result["front_nodes"],path_nm=result["path"],closest_nm=result["closest"]))
extensions=json.loads((root/"cpu-output-existing-copper-vias.json").read_text())
assert extensions["parent_sha256"]==state["sha256"]
trial_sites=sorted({tuple(row[2]) for row in extensions["shortest_extensions"]} | set(source_vias))
source_trunk=[]
if source_vias:
    for layer in (p.In2_Cu,p.In3_Cu):
        req=dict(geometry=geometry(board,layer,coil.GetNetCode()),width=800000,
                 sites=[tuple(via.GetPosition())],target=trial_sites,limit=34000000)
        proc=subprocess.run(["python3",str(tools/"screen_cpu_launch_corridor.py")],input=json.dumps(req),text=True,capture_output=True,check=True)
        result=json.loads(proc.stdout)
        source_trunk.append(dict(layer=board.GetLayerName(layer),width_mm=.8,tested_targets_nm=trial_sites,path_nm=result["path"],closest_nm=result["closest"],reachable_grid_vertices=result["front_nodes"]))
model=[]
# Straight cylindrical copper shell, finished hole taken equal to CAD drill.
for wall_um in (20,25):
    for outer_um in (30,35):
        inner=via.GetDrillValue()/1e6
        area=math.pi*((inner/2+wall_um/1000)**2-(inner/2)**2)
        barrel_r=.01724*(thickness/1000)/area
        neck_r=.01724*(.325/1000)/(.250*outer_um/1000)
        model.append(dict(wall_um=wall_um,outer_copper_um=outer_um,barrel_mohm=barrel_r*1000,front_neck_mohm=neck_r*1000,example_3A_drop_mV=3000*(barrel_r+neck_r),example_3A_loss_mW=9000*(barrel_r+neck_r)))
report=dict(sha256=state["sha256"],coil_xy_nm=target,balls_nm=launch,front_seeds=len(sources),output_vias_nm=all_output_vias,kelvin_nm=sorted(kelvin),power_branch_vias_nm=source_vias,component_to_component_inner_search=source_trunk,front_edge_search=rows,inner_exit_from_hf_via=inner_access,board_thickness_mm=thickness,finished_hole_assumed_mm=inner,hf_path_sensitivity=model,
limits="Scope: grid access from lands within 3 mm. Resistance sensitivity at 20 °C excludes contacts, spreading, package, full trunk and GND. Copper thicknesses and 3 A are hypothetical. No thermal ampacity or DC feed qualified.")
(root/"cpu-trunk-edge-and-resistance.json").write_text(json.dumps(report,indent=2)+"\n")
print(rows,model[0])
