"""Recover short, wide copper between adjacent rear-side bypasses of the rotated PMIC."""
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pcbnew as pcb

from audit_mount_component_reservations import screen
from drc_regression import introduced
import native_front_splice as splice
from pcb_preservation import verify_preservation

root = Path(__file__).resolve().parents[1] / 'migration-rk3562/experiments/phy-power-parallel'
return_pairs='--buck-return-pairs' in sys.argv
base = json.loads((root / ('rotated-bypass-source-mixed.json' if return_pairs else 'rotated-system-supply-pins.json')).read_text())
current = root / base['board']
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert digest(current) == base['sha256']
records = []
held = []
splice.side = pcb.B_Cu
owners = []
def pad(board, name):
    return board.FindFootprintByReference(name).FindPadByNumber('2' if return_pairs else '1')

def members(board, item):
    return {obj.m_Uuid.AsString() for obj in board.GetConnectivity().GetConnectedItems(item)}

names = ['C421','C422','C423','C424','C425','C480','C481','C482','C483','C484','C485']
original = pcb.LoadBoard(str(current))
order = []
for left, right in ([('C421','C431'),('C422','C432'),('C423','C433'),('C424','C434'),('C425','C435')] if return_pairs else itertools.combinations(names, 2)):
    a, z = pad(original, left), pad(original, right)
    net='GND' if return_pairs else '+3V3_SYS'
    if a.GetNetname() != net or z.GetNetname() != net:continue
    distance = math.dist(tuple(a.GetPosition()), tuple(z.GetPosition()))
    if distance <= 4000000: order.append((distance,left,right))

for distance,left,right in sorted(order):
    board = pcb.LoadBoard(str(current))
    owners.append(board)
    board.BuildConnectivity()
    a,z = pad(board,left),pad(board,right)
    if z.m_Uuid.AsString() in members(board,a): continue
    if not all(item.IsOnLayer(pcb.B_Cu) for item in (a,z)): continue
    width=600000 if return_pairs else 500000
    route, info = splice.recover(board,[(tuple(a.GetPosition()),tuple(z.GetPosition()),width,a.GetNetCode())],a.GetNetname(),None,search_all_obstacles=True)
    if route and return_pairs and info['length_mm']>4.2:route=None
    if not route:
        held.append(dict(left=left,right=right,reason=info))
        continue
    for start,end in zip(route,route[1:]):
        board.Add(splice.wire(board,start,end,a.GetNetCode(),width))
    folder = root/'runs'/(('rotated-buck-return-pair-' if return_pairs else 'rotated-bypass-island-')+left+'-'+right)
    folder.mkdir(exist_ok=True)
    for cfg in ('fp-lib-table','phy-joint.kicad_pro','phy-joint.kicad_dru'):
        shutil.copy2(current.parent/cfg,folder/cfg)
    out = folder/current.name
    pcb.ZONE_FILLER(board).Fill(board.Zones())
    pcb.SaveBoard(str(out),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta = introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if delta:
        held.append(dict(left=left,right=right,drc=delta))
        continue
    prior,saved = pcb.LoadBoard(str(current)),pcb.LoadBoard(str(out))
    owners.extend([prior,saved])
    guard = verify_preservation(prior,saved)
    assert pad(saved,right).m_Uuid.AsString() in members(saved,pad(saved,left)) and not screen(saved)
    row = dict(left=left,right=right,width_mm=width/1e6,length_mm=info['length_mm'],preserved_groups=guard['existing_connected_pad_groups_preserved'])
    records.append(row)
    meta = json.loads((current.parent/'output-legs.json').read_text())
    meta.update(board_sha256=digest(out),**({'buck_return_pairs':records} if return_pairs else {'bypass_island_recoveries':records}))
    (folder/'output-legs.json').write_text(json.dumps(meta,indent=2)+'\n')
    current=out
    print(row,flush=True)
report = dict(parent_sha256=base['sha256'],board=str(current.relative_to(root)),sha256=digest(current),records=records,held=held,assembly_ready=False)
(root/('rotated-buck-return-pairs.json' if return_pairs else 'rotated-bypass-islands.json')).write_text(json.dumps(report,indent=2)+'\n')
print(len(records),len(held),flush=True)
os._exit(0)
