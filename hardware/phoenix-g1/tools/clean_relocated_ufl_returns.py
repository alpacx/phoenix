"""Restore the SoC bank ground previously joined by J2001, then prune abandoned tails."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

import pcbnew as p

from drc_regression import introduced
from pcb_preservation import verify_preservation

root = Path(__file__).resolve().parents[1] / "migration-rk3562/experiments/phy-power-parallel"
def checkpoint(name):
    report = json.loads((root / (name + ".json")).read_text())
    report = report.get("candidate", report)
    path = root / report["board"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == report["sha256"]
    return path

before = checkpoint("wifi-selector-branch-coupon")
source = checkpoint("rf-local-shield-return")
folder = root / "runs/rf-extant-ground-cleanup"
folder.mkdir(exist_ok=True)
for name in ("phy-joint.kicad_pro", "phy-joint.kicad_dru", "fp-lib-table"):
    shutil.copy2(source.parent / name, folder / name)
target = folder / source.name
baseline = json.loads((before.parent / "drc.json").read_text())
report = json.loads((source.parent / "drc.json").read_text())
initial = p.LoadBoard(str(before))
board = p.LoadBoard(str(source))
old = {t.m_Uuid.AsString() for t in initial.GetTracks()}
removed = []
keep_alive = [initial, board]
# The old shell land also completed the ground of seven U1 balls.
bridge = p.PCB_TRACK(board)
bridge.SetLayer(p.F_Cu)
bridge.SetNet(board.FindNet("GND"))
bridge.SetStart(p.VECTOR2I(51525000, 17500000))
bridge.SetEnd(p.VECTOR2I(51525000, 18270000))
bridge.SetWidth(500000)
board.Add(bridge)
for iteration in range(12):
    findings = introduced(baseline, report) if iteration else []
    if iteration and not findings:
        break
    tracks = {t.m_Uuid.AsString(): t for t in board.GetTracks()}
    for finding in findings:
        assert finding["type"] in ("track_dangling", "via_dangling"), finding
        identifier, = finding["items"]
        assert identifier in old
        item = tracks[identifier]
        endpoints = [tuple(item.GetPosition())] if isinstance(item, p.PCB_VIA) else [tuple(item.GetStart()), tuple(item.GetEnd())]
        assert item.GetNetname() == "GND"
        for xy in endpoints:
            assert min(math.dist(xy, center) for center in ((53000000, 17500000), (74500000, 22000000))) < 4500000, xy
        removed.append(identifier)
        board.Remove(item)
        keep_alive.append(item)
    p.ZONE_FILLER(board).Fill(board.Zones())
    p.SaveBoard(str(target), board)
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli", "pcb", "drc", "--format", "json", "-o", str(folder / "drc.json"), str(target)], capture_output=True, check=True)
    board = p.LoadBoard(str(target))
    keep_alive.append(board)
    report = json.loads((folder / "drc.json").read_text())
else:
    raise RuntimeError("Residual branch exceeds the bounded cleanup region")
preserved = verify_preservation(initial, board, replaced_copper=removed)
def group(ref, num):
    foot = board.FindFootprintByReference(ref)
    return {pad.m_Uuid.AsString() for pad in board.GetConnectivity().GetConnectedItems(foot.FindPadByNumber(num))}
def contains(group_ids, ref, num):
    return board.FindFootprintByReference(ref).FindPadByNumber(num).m_Uuid.AsString() in group_ids
for anchor, sinks in [(("U4", "69"), [("J2001", "2"), ("J2001", "3"), ("C2008", "2"), ("C2009", "2")]), (("R2001", "2"), [("J2001", "1")]), (("U25", "2"), [("R2001", "1"), ("R2005", "1")])]:
    ids = group(*anchor)
    assert all(contains(ids, *sink) for sink in sinks), (anchor,sinks)
result = dict(board=str(target.relative_to(root)), sha256=hashlib.sha256(target.read_bytes()).hexdigest(), parent_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), baseline_sha256=hashlib.sha256(before.read_bytes()).hexdigest(), soc_bank_ground_bridge_mm=[[51.525,17.500],[51.525,18.270]], bridge_width_mm=0.50, removed_ground_tails=removed, preservation=preserved, new_drc=introduced(baseline, report), assembly_ready=False)
(root / "rf-external-return-cleanup.json").write_text(json.dumps(result, indent=2) + "\n")
print(len(removed),preserved["existing_connected_pad_groups_preserved"],flush=True)
os._exit(0)
