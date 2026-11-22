"""Retain only solder-land repairs whose reference stitches pass the full native PCB checks."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
read=lambda n:json.loads((root/(n+".json")).read_text())
base=read("layout-command-ca1")
moves=read("bga-ordinary-barrels")
returns=read("bga-ordinary-returns")
assert moves["parent_sha256"]==base["sha256"] and returns["parent_sha256"]==moves["sha256"]
def load(d):
    f=root/d["board"]
    assert hashlib.sha256(f.read_bytes()).hexdigest()==d["sha256"]
    return p.LoadBoard(str(f))
b=load(base); trial=load(returns)
uid=lambda o:o.m_Uuid.AsString()
old={uid(t):t for t in b.GetTracks()}
parts={uid(t):t for t in trial.GetTracks()}
chosen={t["signal_via"]:t["accepted"] for t in returns["terminal_results"] if t["accepted"] and t["accepted"]["distance_mm"]<=1}
selected_moves=[t for t in moves["moved"] if t["uuid"] in chosen]
nets={parts[t].GetNetname() for t in chosen}
extra={v["via_uuid"] for v in chosen.values()}|{k for k,t in parts.items() if k not in old and t.GetNetname() in nets}
for k in chosen:old[k].SetPosition(parts[k].GetPosition())
for k in extra:
    t=parts[k].Duplicate();t.SetUuid(parts[k].m_Uuid);b.Add(t)
folder=root/"runs/bga-referenced-barrel";folder.mkdir(exist_ok=True)
src=root/base["board"]
for name in ("phy-joint.kicad_pro","phy-joint.kicad_dru","fp-lib-table"):shutil.copyfile(src.parent/name,folder/name)
out=folder/src.name
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(out)],capture_output=True,check=True)
drc=json.loads((folder/"drc.json").read_text()); delta=introduced(json.loads((src.parent/"drc.json").read_text()),drc)
saved=p.LoadBoard(str(out));saved.BuildConnectivity()
assert not delta and not screen(saved)
proof=verify_preservation(load(base),saved,replaced_copper=chosen)
master=saved.FindFootprintByReference("U4").FindPadByNumber("69")
gnd={uid(o) for o in saved.GetConnectivity().GetConnectedItems(master)}
assert all(a["via_uuid"] in gnd for a in chosen.values())
result=dict(parent_sha256=base["sha256"],board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
            moved=selected_moves,returns=chosen,preservation=proof,new_drc=delta,adopted=False)
(root/"bga-referenced-barrel.json").write_text(json.dumps(result,indent=2)+"\n")
print(selected_moves,len(extra))
