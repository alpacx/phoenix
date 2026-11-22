"""Reconnect A+ using its two complete terminal components after the split pair is placed."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

import pcbnew as p
from pcb_power_leg import make
from phy_corridor_path import geometry
from drc_regression import introduced
from pcb_preservation import verify_preservation

tools=Path(__file__).resolve().parent
root=tools.parent/"migration-rk3562/experiments/phy-power-parallel"
parent=root/"runs/ddr-clock-a-split-copper-positive-ram-extended/phy-joint.kicad_pcb"
baseline=json.loads((root/"ddr-clock-b-preserved-recovered.json").read_text())
base=p.LoadBoard(str(root/baseline["board"]))
ids={t.m_Uuid.AsString() for t in base.GetTracks()}
net="LPDDR4_CLKP_A"
trial=p.LoadBoard(str(parent))
trial.BuildConnectivity()
balls=[next(q for q in trial.FindFootprintByReference(ref).Pads() if q.GetNetname()==net) for ref in ("U1","U2")]
terminal=[]
for ball in balls:
    group={q.m_Uuid.AsString() for q in trial.GetConnectivity().GetConnectedItems(ball)}
    vias=[v for v in trial.GetTracks() if isinstance(v,p.PCB_VIA) and v.m_Uuid.AsString() in group]
    terminal.append(tuple((next(v for v in vias if v.m_Uuid.AsString() not in ids) if len(vias)>1 else vias[0]).GetPosition()))
removed=[]
code=balls[0].GetNetCode()
original_obstacles=geometry(trial,p.F_Cu,code,oval_caps=True)
for t in list(trial.GetTracks()):
    if t.GetLayer()==p.F_Cu and t.GetNetname()==net and t.m_Uuid.AsString() not in ids and not isinstance(t,p.PCB_VIA):
        removed.append(t.m_Uuid.AsString())
data=json.loads(Path("/tmp/phoenix-clock-a-F.Cu.json").read_text())
req=dict(via_nm=terminal,plane=data["plane"],geometry=[*original_obstacles,data["geometry"][2]],compact_45=True,reference_half_width_nm=200000,max_path_nm=7500000)
result=json.loads(subprocess.run(["python3",str(tools/"ddr_plane_grid.py")],input=json.dumps(req),text=True,capture_output=True,check=True).stdout)
report={"parent_sha256":hashlib.sha256(parent.read_bytes()).hexdigest(),"terminal_nm":terminal,"removed_trial_pieces":removed,"result":result,"adopted":False}
if "path" in result:
    for t in list(trial.GetTracks()):
        if t.m_Uuid.AsString() in removed:
            trial.Remove(t)
    for a,z in zip(result["path"],result["path"][1:]):trial.Add(make(trial,a,z,200000,code,p.F_Cu))
    folder=root/"runs/ddr-clock-a-split-clean-launch"
    folder.mkdir(exist_ok=True)
    for fn in ("phy-joint.kicad_pro","phy-joint.kicad_dru","fp-lib-table"):shutil.copyfile(parent.parent/fn,folder/fn)
    out=folder/parent.name
    p.ZONE_FILLER(trial).Fill(trial.Zones())
    p.SaveBoard(str(out),trial)
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(out)],capture_output=True,check=True)
    report["drc_delta"]=introduced(json.loads(((root/baseline["board"]).parent/"drc.json").read_text()),json.loads((folder/"drc.json").read_text()))
    b=p.LoadBoard(str(out));b.BuildConnectivity()
    report["proof"]=verify_preservation(base,b)
    report["sha256"]=hashlib.sha256(out.read_bytes()).hexdigest()
(root/"ddr-clock-a-split-clean-launch.json").write_text(json.dumps(report,indent=2)+"\n")
print(result)
