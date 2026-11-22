"""Recover a displaced PHY reset trace on F.Cu while escaping U25.13 on B.Cu."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import pcbnew as p
from native_front_splice import compact, recover, wire
from pcb_power_leg import make, barrel
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

stage = Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
read = lambda n: json.loads((stage/n).read_text())
base = read("wifi_host_wake-service-launch.json")["candidate"]
window = read("wifi-host-wake-radio-window.json")
source = stage/base["board"]
assert base["sha256"] == window["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
assert window["surface"] == "B.Cu"
folder = stage/"runs/radio-wake-reset-rework"
folder.mkdir(exist_ok=True)
for config in ("phy-joint.kicad_pro", "phy-joint.kicad_dru", "fp-lib-table"):
    shutil.copy2(source.parent/config, folder/config)
original = p.LoadBoard(str(source))
uid = lambda item: item.m_Uuid.AsString()
trials = []
winner = None
for row in sorted(window["single_obstacle_candidates"], key=lambda r:len(r["obstacles"])):
    if row["name"] != "PHY_RESET_N" or any(layer != "F.Cu" for _,layer in row["obstacles"]):
        continue
    b = p.LoadBoard(str(source))
    replaced = {i for i,_ in row["obstacles"]}
    items = [t for t in b.GetTracks() if uid(t) in replaced]
    assert len(items) == len(replaced)
    if any(isinstance(t,p.PCB_VIA) for t in items):
        continue
    old = [(tuple(t.GetStart()),tuple(t.GetEnd()),t.GetWidth(),t.GetNetCode()) for t in items]
    for t in items:
        b.Remove(t)
    pin = b.FindFootprintByReference("U25").FindPadByNumber("13")
    pts = compact(row["path_nm"])
    for a,z in zip(pts,pts[1:]):
        b.Add(make(b,a,z,200000,pin.GetNetCode(),p.B_Cu))
    via = barrel(b,pts[-1],pin.GetNetCode())
    vid = uid(via)
    b.Add(via)
    recovered, info = recover(b,old,"PHY_RESET_N",False,search_all_obstacles=True,exact_start=True,exact_destination=True)
    trial = dict(via_nm=pts[-1],replaced=sorted(replaced),recovery=info)
    trials.append(trial)
    if not recovered:
        continue
    for a,z in zip(recovered,recovered[1:]):
        b.Add(wire(b,a,z,info["code"],info["width"]))
    out = folder/source.name
    p.ZONE_FILLER(b).Fill(b.Zones())
    p.SaveBoard(str(out),b)
    dr = folder/"drc.json"
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(dr),str(out)],check=True,capture_output=True)
    delta = introduced(json.loads((source.parent/"drc.json").read_text()),json.loads(dr.read_text()))
    trial["new_drc"] = delta
    if any(r["type"]!="via_dangling" or r["items"]!=[vid] for r in delta):
        continue
    saved = p.LoadBoard(str(out))
    saved.BuildConnectivity()
    q = saved.FindFootprintByReference("U25").FindPadByNumber("13")
    if vid not in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(q)} or screen(saved):
        continue
    guard = verify_preservation(original,saved,replaced_copper=replaced)
    winner = dict(board=str(out.relative_to(stage)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
                  via_uuid=vid,replaced=sorted(replaced),preservation=guard)
    break
(stage/"radio-wake-reset-rework.json").write_text(json.dumps(dict(parent_sha256=base["sha256"],candidate=winner,trials=trials,assembly_ready=False),indent=2)+"\n")
print("trials",len(trials),"candidate",bool(winner))
