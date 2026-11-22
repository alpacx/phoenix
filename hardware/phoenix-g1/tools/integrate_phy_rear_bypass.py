"""Replay the verified PHY bypass on the current board, preserving unrelated copper."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_preservation import verify_preservation

root = Path(__file__).resolve().parents[1] / 'migration-rk3562/experiments/phy-power-parallel'
def load(name):
    report = json.loads((root/(name+'.json')).read_text())
    path = root/report['board']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == report['sha256']
    return report,path,p.LoadBoard(str(path))

def tracks(board):
    return {t.m_Uuid.AsString():t for t in board.GetTracks()}

parent,source,board = load('layout-outer-ground-mesh')
before,_,original = load('layout-phy-full-feed')
clock,_,_clock_board = load('phy-clock-load-window')
trial,_,tested = load('rear-c518-bent-existing-return-fresh')
assert trial['change'] and clock['parent_sha256']==before['sha256'] and trial['parent_sha256']==clock['sha256']
start,end,live=map(tracks,(original,tested,board))
removed=set(start)-set(end)
assert len(removed)==6 and all(live[k].GetNetname()=='GND' for k in removed)
for k in removed:
    board.Remove(live[k])
for ref in ('C520','C518'):
    part=board.FindFootprintByReference(ref)
    source_part=tested.FindFootprintByReference(ref)
    if source_part.GetLayer()!=part.GetLayer():
        part.Flip(part.GetPosition(),False)
    part.SetOrientation(source_part.GetOrientation())
    part.SetPosition(source_part.GetPosition())
for k in set(end)-set(start):
    item=end[k].Duplicate()
    item.SetNetCode(board.GetNetcodeFromNetname(end[k].GetNetname()))
    board.Add(item)
folder=root/'runs/phy-pin40-integrated'
folder.mkdir(exist_ok=True)
for name in ('fp-lib-table','phy-joint.kicad_pro','phy-joint.kicad_dru'):
    shutil.copy2(source.parent/name,folder/name)
out=folder/source.name
p.ZONE_FILLER(board).Fill(board.Zones())
p.SaveBoard(str(out),board)
drc=folder/'drc.json'
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
delta=introduced(json.loads((source.parent/'drc.json').read_text()),json.loads(drc.read_text()))
assert not delta,delta
saved=p.LoadBoard(str(out))
saved.BuildConnectivity()
proof=verify_preservation(p.LoadBoard(str(source)),saved,replaced_copper=removed)
assert not screen(saved)
def linked(pair):
    pads=[saved.FindFootprintByReference(r).FindPadByNumber(n) for r,n in (a.split('.') for a in pair)]
    return pads[1].m_Uuid.AsString() in {k.m_Uuid.AsString() for k in saved.GetConnectivity().GetConnectedItems(pads[0])}
extra=[['U5.40','C518.1'],['C518.2','C511.2'],['C520.2','C511.2']]
assert all(linked(pair) for pair in parent['verified_pairs']+extra)
assert not linked(['C518.1','C515.1'])
result=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=parent['sha256'],pairs=extra,preservation=proof,assembly_ready=False)
(root/'phy-pin40-integrated.json').write_text(json.dumps(result,indent=2)+'\n')
print(extra,flush=True)
os._exit(0)
