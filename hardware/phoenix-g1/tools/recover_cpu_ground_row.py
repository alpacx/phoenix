"""Test CPU and ground as coupled requirements at the only single-track opening under the package."""
import json
import sys
import hashlib
import math
import subprocess
from pathlib import Path

import pcbnew as p
from phy_corridor_path import geometry
from pcb_power_leg import make,barrel
from pcb_bounds import inflated_box
from drc_regression import introduced
from pcb_preservation import verify_preservation

tools=Path(__file__).resolve().parent
root=tools.parent/"migration-rk3562/experiments/phy-power-parallel"
read=lambda n:json.loads((root/(n+".json")).read_text())
base=read("layout-bga-referenced-barrel")
file=root/base["board"];assert hashlib.sha256(file.read_bytes()).hexdigest()==base["sha256"]
b=p.LoadBoard(str(file));soc=b.FindFootprintByReference("U1")
barrier=next(t for t in b.GetTracks() if t.m_Uuid.AsString()=="5b43d5da-3484-47e8-bc7d-22355cba3a8f")
b.Remove(barrier);b.BuildConnectivity()
pos=(41750000,18750000);c=soc.FindPadByNumber("1H6").GetNetCode()
g=soc.FindPadByNumber("1F5").GetNetCode()
caps=[o for o in soc.Pads() if o.GetNetCode()==c]
grounded={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference("U4").FindPadByNumber("69"))}
gsrc=soc.FindPadByNumber("1F5")
sinks=[q for q in soc.Pads() if q.m_Uuid.AsString() in grounded and math.dist(tuple(q.GetPosition()),tuple(gsrc.GetPosition()))<2400000]
cvia=barrel(b,pos,c);b.Add(cvia)
native="--native-soc-spacing" in sys.argv
def geometry_for(code):
    tracks,pads=geometry(b,p.F_Cu,code,oval_caps=True)
    if native and code==c:
        # Existing U1 land spacing rule is 0.0762 mm. Retain 0.102 mm
        # to U1's individual lands while keeping all track spacings at 0.202 mm.
        bounds=set()
        for q in soc.Pads():
            if q.IsOnLayer(p.F_Cu) and q.GetNetCode()!=c:
                bb=q.GetBoundingBox();bounds.add((bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom()))
        pads=[(x+100000,y+100000,z-100000,w-100000) if (x,y,z,w) in bounds else (x,y,z,w) for x,y,z,w in pads]
    return tracks,pads
def search_space(geo,width,sites,target,limit,collect=False):
    req=dict(geometry=geo,width=width,sites=sites,target=target,limit=limit,frontier=collect)
    result=subprocess.run(["python3",str(tools/"screen_cpu_launch_corridor.py")],input=json.dumps(req),text=True,capture_output=True,check=True)
    return json.loads(result.stdout)
ground=search_space(geometry_for(g),300000,[tuple(gsrc.GetPosition())],[tuple(q.GetPosition()) for q in sinks],4000000)
if ground.get("path"):
    for a,z in zip(ground["path"],ground["path"][1:]):b.Add(make(b,a,z,300000,g,p.F_Cu))
cpu=search_space(geometry_for(c),200000 if native else 250000,[tuple(q.GetPosition()) for q in caps],[pos],4500000,True)
back=search_space(geometry_for(c),200000 if native else 250000,[pos],[tuple(q.GetPosition()) for q in caps],4500000,True)
fronts=[cpu.pop("front"),back.pop("front")]
closest=min(((math.dist(a,z),a,z) for a in fronts[0] for z in fronts[1]),default=None)
barrier_tags=[]
if closest:
    trace=make(b,closest[1],closest[2],250000,c,p.F_Cu);seg=trace.GetEffectiveShape(p.F_Cu);bb=inflated_box(trace,260000)
    for obj in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]:
        if not obj.IsOnLayer(p.F_Cu) or obj.GetNetCode()==c or not bb.Intersects(obj.GetBoundingBox()):continue
        if seg.Collide(obj.GetEffectiveShape(p.F_Cu),202000):
            barrier_tags.append(dict(uuid=obj.m_Uuid.AsString(),name=obj.GetNetname(),kind=obj.GetClass(),pad=obj.GetNumber() if isinstance(obj,p.PAD) else None))
report={"parent_sha256":base["sha256"],"ground":ground,"cpu_branch":cpu,"site_nm":pos,"via_front":back,"closest_fronts":closest,"front_barriers":barrier_tags}
(root/("cpu-ground-row-native-pad-spacing.json" if native else "cpu-ground-row-and-drop.json")).write_text(json.dumps(report,indent=2)+"\n")
print(ground,cpu,closest,barrier_tags)
