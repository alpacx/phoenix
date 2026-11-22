"""Escape the USB orientation pin through the space released by the relocated memory bypass."""
import hashlib
import json
import os
import sys
from pathlib import Path
import shutil
import subprocess

import pcbnew as pcb
from drc_regression import introduced
from native_front_splice import compact
from pcb_power_leg import barrel, make
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
service=next((n for n in ('PMIC_INT_N','WIFI_HOST_WAKE') if n in sys.argv),None)
base=json.loads((root/('layout-gpu-cap-bank.json' if service else 'layout-memory-bank-c1665.json')).read_text())
window=json.loads((root/(service.lower()+'-service-window.json' if service else 'usb-dir-c1665-released-window.json')).read_text())
source=root/base['board']
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
assert digest(source)==window['source_sha256']==base['sha256']
original=pcb.LoadBoard(str(source))
ref,pin=window['pin'].split('.') if service else ('U6','11')
label=service.lower()+'-service-launch' if service else 'usb-orientation-released-escape'
folder=root/'runs'/label;folder.mkdir(exist_ok=True)
for cfg in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source.parent/cfg,folder/cfg)
winner=None
def uid(item):return item.m_Uuid.AsString()
for site in window['sites']:
    board=pcb.LoadBoard(str(source));q=board.FindFootprintByReference(ref).FindPadByNumber(pin)
    net=q.GetNetCode()
    pts=compact([tuple(x) for x in site['path_nm']])
    for a,z in zip(pts,pts[1:]):board.Add(make(board,a,z,200000,net,pcb.F_Cu))
    via=barrel(board,pts[-1],net);board.Add(via)
    out=folder/source.name;pcb.ZONE_FILLER(board).Fill(board.Zones());pcb.SaveBoard(str(out),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((source.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if any(r['type']!='via_dangling' or r['items']!=[uid(via)] for r in delta):continue
    saved=pcb.LoadBoard(str(out));guard=verify_preservation(original,saved)
    assert uid(via) in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference(ref).FindPadByNumber(pin))}
    winner=dict(board=str(out.relative_to(root)),sha256=digest(out),via_uuid=uid(via),via_nm=pts[-1],length_mm=site['length_mm'],new_drc=delta,preservation=guard)
    break
(root/(label+'.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=winner,assembly_ready=False),indent=2)+'\n')
print(winner and winner['via_nm'],flush=True);os._exit(0)
