"""Diagnostic clock-first PCB: release only unfinished memory signal escape vias around both packages."""
from pathlib import Path
import hashlib
import json
import shutil
import os
import sys
import subprocess
import pcbnew as p

r=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
base=json.loads((r/"layout-command-ca1.json").read_text());src=r/base["board"]
assert hashlib.sha256(src.read_bytes()).hexdigest()==base["sha256"]
folder=r/"runs/ddr-clock-open-escape-release";folder.mkdir(exist_ok=True)
out=folder/src.name
if "--verify" not in sys.argv:
    b=p.LoadBoard(str(src));b.BuildConnectivity()
    prior=json.loads((src.parent/"drc.json").read_text())
    dangling={item["uuid"] for v in prior["violations"] if v["type"]=="via_dangling" for item in v["items"]}
    released=[]
    for v in list(b.GetTracks()):
        name=v.GetNetname()
        if not isinstance(v,p.PCB_VIA) or v.m_Uuid.AsString() not in dangling:continue
        if not name.startswith("LPDDR4_") or name.startswith(("LPDDR4_CLKP","LPDDR4_CLKN")):continue
        if name not in base["open_nets"]:continue
        released.append({"net":name,"uuid":v.m_Uuid.AsString(),"location_nm":tuple(v.GetPosition())})
        b.Remove(v)
    for part in ("fp-lib-table","phy-joint.kicad_dru","phy-joint.kicad_pro"):shutil.copyfile(src.parent/part,folder/part)
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(folder/"drc.json"),str(out)],capture_output=True,check=True)
    (folder/"released.json").write_text(json.dumps(released,indent=2)+"\n")
    os.execv(sys.executable,[sys.executable,__file__,"--verify"])
released=json.loads((folder/"released.json").read_text())
saved=p.LoadBoard(str(out));saved.BuildConnectivity()
def terminal(name):
    ref,num=name.split(".")
    return saved.FindFootprintByReference(ref).FindPadByNumber(num)
validated=0
groups={}
for a,z in base["verified_pairs"]:
    if a not in groups:groups[a]={o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(terminal(a))}
    assert terminal(z).m_Uuid.AsString() in groups[a],(a,z)
    validated+=1
report={"parent_sha256":base["sha256"],"sha256":hashlib.sha256(out.read_bytes()).hexdigest(),"board":str(out.relative_to(r)),"released":released,"preserved_pad_pairs":validated,"adopted":False,
        "scope":"Released only native dangling through vias on still-open LPDDR4 signal nets, keeping both clock pairs. Every released escape must be rebuilt before replacing the original. This is a clock corridor diagnostic."}
(r/"ddr-clock-open-escape-release.json").write_text(json.dumps(report,indent=2)+"\n")
print(len(released),validated)
