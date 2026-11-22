"""Route both F.Cu terminal leads without imposing a pre-drawn trunk or polarity ordering."""
from pathlib import Path
import json
import hashlib
import shutil
import subprocess

import pcbnew as p
from pcb_power_leg import make
from phy_corridor_path import geometry
from drc_regression import introduced
from pcb_preservation import verify_preservation

tools=Path(__file__).resolve().parent
root=tools.parent/"migration-rk3562/experiments/phy-power-parallel"
base_meta=json.loads((root/"ddr-clock-b-preserved-recovered.json").read_text())
parent=root/"runs/ddr-clock-a-split-copper-positive-ram-extended/phy-joint.kicad_pcb"
trial=p.LoadBoard(str(parent));base=p.LoadBoard(str(root/base_meta["board"]))
baseline_ids={t.m_Uuid.AsString() for t in base.GetTracks()}
sections=max(json.loads((root/"ddr-clock-a-split-copper-positive-ram-extended.json").read_text())["attempts"],key=lambda t:t["joined"])["sections"]
phases=["LPDDR4_CLKP_A","LPDDR4_CLKN_A"]
front_template=json.loads(Path("/tmp/phoenix-clock-a-F.Cu.json").read_text())
attempts=[]
for ordered in (phases,phases[::-1]):
    board=p.LoadBoard(str(root/base_meta["board"]))
    for t in trial.GetTracks():
        if t.m_Uuid.AsString() in baseline_ids:continue
        if not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu:continue
        clone=t.Duplicate();clone.SetUuid(t.m_Uuid);board.Add(clone)
    records=[]
    for phase in ordered:
        ends=[s["origin"] for s in sections if s["phase"]==phase and s["layer"]=="F.Cu"]
        code=board.FindNet(phase).GetNetCode()
        req=dict(via_nm=ends,plane=front_template["plane"],geometry=[*geometry(board,p.F_Cu,code,oval_caps=True),front_template["geometry"][2]],compact_45=True,reference_half_width_nm=200000,max_path_nm=8500000)
        out=subprocess.run(["python3",str(tools/"ddr_plane_grid.py")],input=json.dumps(req),text=True,capture_output=True,check=True)
        result=json.loads(out.stdout);records.append({"net":phase,"result":result})
        path=result.get("path",[])
        for a,z in zip(path,path[1:]):board.Add(make(board,a,z,200000,code,p.F_Cu))
    attempts.append(records)
    if not all("path" in rec["result"] for rec in records):continue
    folder=root/"runs/ddr-clock-a-front-pair";folder.mkdir(exist_ok=True)
    for f in ("phy-joint.kicad_pro","phy-joint.kicad_dru","fp-lib-table"):shutil.copyfile(parent.parent/f,folder/f)
    file=folder/parent.name
    p.ZONE_FILLER(board).Fill(board.Zones())
    p.SaveBoard(str(file),board)
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(file)],capture_output=True,check=True)
    drc=json.loads((folder/"drc.json").read_text())
    d0=json.loads(((root/base_meta["board"]).parent/"drc.json").read_text())
    records.append({"board_sha256":hashlib.sha256(file.read_bytes()).hexdigest(),"native_delta":introduced(d0,drc),"preservation":verify_preservation(base,p.LoadBoard(str(file)))})
    break
(root/"ddr-clock-a-front-pair.json").write_text(json.dumps({"parent_sha256":hashlib.sha256(parent.read_bytes()).hexdigest(),"attempts":attempts,"adopted":False},indent=2)+"\n")
print([[bool(x.get("result",{}).get("path")) for x in a] for a in attempts])
