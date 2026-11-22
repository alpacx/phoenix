"""Build the two-layer clock A candidate and check its eight local joins against actual copper."""
from pathlib import Path
import hashlib
import itertools
import json
import math
import shutil
import subprocess
import sys

import pcbnew as p

from pcb_power_leg import make, barrel
from phy_corridor_path import geometry
from drc_regression import introduced
from pcb_preservation import verify_preservation

tools=Path(__file__).resolve().parent
root=tools.parent/"migration-rk3562/experiments/phy-power-parallel"
read=lambda filename:json.loads((root/filename).read_text())
meta=read("ddr-clock-b-preserved-recovered.json")
src=root/meta["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta["sha256"]
suffix = "-positive-ram" if "--positive-ram" in sys.argv else ""
trial=read("ddr-clock-a-split-trunks"+suffix+".json")["attempts"][-1]
phases=("LPDDR4_CLKP_A","LPDDR4_CLKN_A")
layers=(p.F_Cu,p.In2_Cu)
middle=[]
for leg in trial["legs"]:
    output=subprocess.run(["python3",str(tools/"make_clock_center_offsets.py")],input=json.dumps(leg),text=True,capture_output=True,check=True)
    middle.append(json.loads(output.stdout))
if suffix:
    # Stop both differential trunks 0.6 mm before the transfer, reserving
    # a launch region around the two 0.45 mm pads on each routing layer.
    for layer,paths in enumerate(middle):
        for j,path in enumerate(paths):
            if layer == 0:
                path.reverse()
            reserve = 600000
            while len(path)>1 and reserve:
                a,z=path[:2]
                length=math.dist(a,z)
                if length<=reserve:
                    reserve-=length
                    path.pop(0)
                else:
                    path[0]=[round(v+(w-v)*reserve/length) for v,w in zip(a,z)]
                    reserve=0
            if layer == 0:
                path.reverse()
if "--extend-terminal" in sys.argv:
    suffix += "-extended"
if "--extend-transfer" in sys.argv:
    suffix += "-transfer"
reference=json.loads(Path("/tmp/phoenix-clock-a-F.Cu.json").read_text())["plane"]
sites=trial["site"]["position_nm"]
original=p.LoadBoard(str(src))
original.BuildConnectivity()
anchors={}
for phase in phases:
    arr=[]
    for ref in ("U1","U2"):
        ball=next(q for q in original.FindFootprintByReference(ref).Pads() if q.GetNetname()==phase)
        ids={t.m_Uuid.AsString() for t in original.GetConnectivity().GetConnectedItems(ball)}
        v,=[t for t in original.GetTracks() if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() in ids]
        arr.append(tuple(v.GetPosition()))
    anchors[phase]=arr
attempts=[]
best_partial=0
def ends(i,f0,f1,swap):
    a,b=anchors[phases[i]]
    s=sites[i^swap]
    t,u=middle[0][i^f0],middle[1][i^f1]
    return [(0,a,t[0]),(0,s,t[-1]),(1,s,u[0]),(1,b,u[-1])]
def score(permutation):
    return sum(math.dist(a,z) for i in range(2) for _,a,z in ends(i,*permutation))
for perm in sorted(itertools.product((0,1),repeat=3),key=score):
    b=p.LoadBoard(str(src))
    for i,phase in enumerate(phases):
        code=b.FindNet(phase).GetNetCode()
        b.Add(barrel(b,sites[i^perm[2]],code))
        for l,which in enumerate(perm[:2]):
            path=middle[l][i^which]
            for a,z in zip(path,path[1:]):b.Add(make(b,a,z,200000,code,layers[l]))
    results=[]
    for i,phase in enumerate(phases):
        code=b.FindNet(phase).GetNetCode()
        for l,a,z in ends(i,*perm):
            layer=layers[l]
            keepouts=json.loads(Path("/tmp/phoenix-clock-a-"+b.GetLayerName(layer)+".json").read_text())["geometry"][2]
            req=dict(via_nm=[a,z],plane=reference,geometry=[*geometry(b,layer,code,oval_caps=True),keepouts],compact_45=True,reference_half_width_nm=200000,max_path_nm=(7000000 if ("--extend-terminal" in sys.argv and l==1 and a==anchors[phase][1]) or ("--extend-transfer" in sys.argv and l==0 and a in sites) else 3500000))
            output=subprocess.run(["python3",str(tools/"ddr_plane_grid.py")],input=json.dumps(req),text=True,capture_output=True,check=True)
            result=json.loads(output.stdout)
            results.append(dict(phase=phase,layer=b.GetLayerName(layer),origin=a,tip=z,result=result))
            path=result.get("path",[])
            for start,end in zip(path,path[1:]):b.Add(make(b,start,end,200000,code,layer))
    joined=sum("path" in row["result"] for row in results)
    attempts.append(dict(orientation=perm,joined=joined,sections=results))
    if joined<8 and joined<=best_partial:continue
    best_partial=max(best_partial,joined)
    folder=root/("runs/ddr-clock-a-split-copper"+suffix)
    folder.mkdir(exist_ok=True)
    for name in ("phy-joint.kicad_pro","phy-joint.kicad_dru","fp-lib-table"):shutil.copyfile(src.parent/name,folder/name)
    out=folder/src.name
    p.ZONE_FILLER(b).Fill(b.Zones())
    p.SaveBoard(str(out),b)
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads((src.parent/"drc.json").read_text()),json.loads((folder/"drc.json").read_text()))
    attempts[-1]["drc_delta"]=delta
    if not delta and joined==8:
        saved=p.LoadBoard(str(out));saved.BuildConnectivity()
        attempts[-1]["preservation"]=verify_preservation(original,saved)
        for phase in phases:
            balls=[next(q for q in saved.FindFootprintByReference(ref).Pads() if q.GetNetname()==phase) for ref in ("U1","U2")]
            assert balls[1].m_Uuid.AsString() in {t.m_Uuid.AsString() for t in saved.GetConnectivity().GetConnectedItems(balls[0])}
        break
(root/("ddr-clock-a-split-copper"+suffix+".json")).write_text(json.dumps({"board_sha256":meta["sha256"],"attempts":attempts,"adopted":False},indent=2)+"\n")
print([t["joined"] for t in attempts])
