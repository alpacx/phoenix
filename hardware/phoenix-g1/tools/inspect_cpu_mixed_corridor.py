"""Find common legal area for a single In2/In3 power transition in a bounded window."""
import json
import hashlib
import subprocess
import sys
from pathlib import Path
import pcbnew as p
from phy_corridor_path import geometry

tools=Path(__file__).resolve().parent
root=tools.parent/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'layout-cpu-local-hf-bypass.json').read_text())
file=root/cp['board'];assert hashlib.sha256(file.read_bytes()).hexdigest()==cp['sha256']
board=p.LoadBoard(str(file));code=board.FindNet('VDD_CPU').GetNetCode()
prev=json.loads((root/'cpu-trunk-edge-and-resistance.json').read_text())
assert prev['sha256']==cp['sha256']
start=(42025000,20325000);targets=prev['component_to_component_inner_search'][0]['tested_targets_nm']
divert="--divert-3v3" in sys.argv
release="--control-relocation" in sys.argv or divert
removed=[]
if release:
    for track in list(board.GetTracks()):
        if not isinstance(track,p.PCB_VIA) and track.GetLayer() in (p.In2_Cu,p.In3_Cu) and track.GetNetname() in ("EXP_GPIO0","EXP_SPI_MOSI"):
            removed.append(track);board.Remove(track)
if divert:
    import math
    from pcb_power_leg import make
    t=next(t for t in board.GetTracks() if t.m_Uuid.AsString()=="e005d37e-27fa-41b7-9868-b245c69ee3ec")
    a,z=tuple(t.GetStart()),tuple(t.GetEnd());vx=z[0]-a[0];vy=z[1]-a[1];length=math.hypot(vx,vy)
    # Keep the +3V3_IO width and both ends; displace only at the diagnosed bottleneck.
    at=lambda x: (x,round(a[1]+(x-a[0])*vy/vx))
    mid1,mid2=at(52100000),at(55400000)
    depth=1500000
    points=[a,at(50500000),(mid1[0]+round(-vy/length*depth),mid1[1]+round(vx/length*depth)),(mid2[0]+round(-vy/length*depth),mid2[1]+round(vx/length*depth)),at(57100000),z]
    board.Remove(t);removed.append(t)
    for u,v in zip(points,points[1:]):board.Add(make(board,u,v,t.GetWidth(),t.GetNetCode(),t.GetLayer()))
tracks=[geometry(board,l,code) for l in (p.In2_Cu,p.In3_Cu)]
vias=[geometry(board,l,code) for l in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)]
lands=[q.GetBoundingBox() for f in board.GetFootprints() for q in f.Pads()]
data=dict(start=start,targets=targets,tracks=tracks,vias=vias,lands=[[b.GetLeft(),b.GetTop(),b.GetRight(),b.GetBottom()] for b in lands])
proc=subprocess.run(['python3',str(tools/'cpu_corridor_regions.py')],input=json.dumps(data),text=True,capture_output=True,check=True)
result=json.loads(proc.stdout);result['sha256']=cp['sha256']
for row in result["orders"]:
    hits=[]
    for layer_idx,point in zip(row["order"],row.get("closest_points_nm",[])):
        layer=(p.In2_Cu,p.In3_Cu)[layer_idx];center=p.VECTOR2I(*map(round,point))
        names=[]
        for track in board.GetTracks():
            if track.GetNetCode()==code or not track.IsOnLayer(layer):continue
            if track.GetEffectiveShape(layer).Collide(center,605000):
                names.append(dict(net=track.GetNetname(),kind=track.GetClass(),uuid=track.m_Uuid.AsString()))
        hits.append(names)
    row["boundary_copper"]=hits
result['diagnostic_copper_removed']=len(removed)
(root/('cpu-mixed-layer-3v3-diversion.json' if divert else 'cpu-mixed-layer-control-relocation.json' if release else 'cpu-mixed-layer-corridor.json')).write_text(json.dumps(result,indent=2)+'\n');print(result)
