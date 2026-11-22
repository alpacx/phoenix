"""Tie a rear-side bypass bank to the system rail with two previously connected plated barrels."""
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

import pcbnew as pcb

from audit_mount_component_reservations import screen
from drc_regression import introduced
import native_front_splice as splice
from pcb_preservation import verify_preservation

root = Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base = json.loads((root/'rotated-bypass-islands.json').read_text())
source = root/base['board']
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert digest(source) == base['sha256']
board = pcb.LoadBoard(str(source))
board.BuildConnectivity()
def pad(board, name, number='1'):
    return board.FindFootprintByReference(name).FindPadByNumber(number)
def group(board, item):
    return {obj.m_Uuid.AsString() for obj in board.GetConnectivity().GetConnectedItems(item)}
source_group = group(board,pad(board,'C1304'))
barrels = [via for via in board.GetTracks() if isinstance(via,pcb.PCB_VIA)
           and via.GetViaType()==pcb.VIATYPE_THROUGH and via.GetDrillValue()>=200000
           and via.GetWidth(pcb.F_Cu)>=450000 and via.m_Uuid.AsString() in source_group]
splice.side = pcb.B_Cu
held = []
candidates = []
for name in ('C483','C423','C482','C485'):
    q=pad(board,name)
    if q.m_Uuid.AsString() in source_group: continue
    origin=tuple(q.GetPosition())
    nearby=[v for v in barrels if math.dist(origin,tuple(v.GetPosition())) <= 4200000]
    legal=[]
    for via in nearby:
        dest=tuple(via.GetPosition())
        path,info=splice.recover(board,[(origin,dest,500000,q.GetNetCode())],q.GetNetname(),None,search_all_obstacles=True)
        if path and path[-1]==dest: legal.append((via,path,info['length_mm']))
    held.append(dict(capacitor=name,reachable=len(legal),available=len(nearby)))
    for first,second in itertools.combinations(legal,2):
        gap=math.dist(first[1][-1],second[1][-1])
        if not 500000<=gap<=1300000:continue
        candidates.append((first[2]+second[2],name,first,second))
winner=None
for _,name,first,second in sorted(candidates,key=lambda item:item[0]):
    b=pcb.LoadBoard(str(source))
    q=pad(b,name)
    for _,path,_ in (first,second):
        for a,z in zip(path,path[1:]): b.Add(splice.wire(b,a,z,q.GetNetCode(),500000))
    folder=root/'runs'/('rotated-paired-bypass-feed-'+name)
    folder.mkdir(exist_ok=True)
    for cfg in ('fp-lib-table','phy-joint.kicad_pro','phy-joint.kicad_dru'):
        shutil.copy2(source.parent/cfg,folder/cfg)
    out=folder/source.name
    pcb.ZONE_FILLER(b).Fill(b.Zones())
    pcb.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads((source.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if delta:
        held.append(dict(capacitor=name,new_drc=delta))
        continue
    saved=pcb.LoadBoard(str(out))
    guard=verify_preservation(board,saved)
    rail=group(saved,pad(saved,'C1304'))
    assert pad(saved,name).m_Uuid.AsString() in rail and not screen(saved)
    winner=dict(capacitor=name,board=str(out.relative_to(root)),sha256=digest(out),barrels=[dict(uuid=v.m_Uuid.AsString(),drill_mm=v.GetDrillValue()/1e6,route_mm=length) for v,_,length in (first,second)],preserved_groups=guard['existing_connected_pad_groups_preserved'])
    meta=json.loads((source.parent/'output-legs.json').read_text());meta.update(board_sha256=digest(out),rear_bank_supply=winner)
    (folder/'output-legs.json').write_text(json.dumps(meta,indent=2)+'\n')
    break
(root/'rotated-paired-bypass-feed.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=winner,held=held,assembly_ready=False),indent=2)+'\n')
print(winner,held,flush=True)
os._exit(0)
