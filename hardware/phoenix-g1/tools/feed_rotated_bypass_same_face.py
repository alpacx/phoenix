"""Connect bypasses to nearby wide tracks already in the bulk capacitor's physical group."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

import pcbnew as pcb
import native_front_splice as splice
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_preservation import verify_preservation

root = Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base = json.loads((root/'rotated-bypass-source-mixed.json').read_text())
current = root/base['board']
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert digest(current) == base['sha256']

def pad(board,ref):
    return board.FindFootprintByReference(ref).FindPadByNumber('1')

def members(board,ref):
    return {obj.m_Uuid.AsString() for obj in board.GetConnectivity().GetConnectedItems(pad(board,ref))}

def nearby_taps(board,rail,side,pt,width,radius):
    points=set()
    for line in board.GetTracks():
        if line.m_Uuid.AsString() not in rail or isinstance(line,pcb.PCB_VIA) or line.GetLayer()!=side or line.GetWidth()<width:continue
        start,end=tuple(line.GetStart()),tuple(line.GetEnd())
        dx,dy=end[0]-start[0],end[1]-start[1]
        frac=min(1,max(0,((pt[0]-start[0])*dx+(pt[1]-start[1])*dy)/max(1,dx*dx+dy*dy)))
        nearest=round(start[0]+dx*frac),round(start[1]+dy*frac)
        points.update(x for x in (nearest,start,end) if math.dist(pt,x)<=radius)
    selected=[]
    for xy in sorted(points,key=lambda a:math.dist(a,pt)):
        if all(math.dist(xy,prior)>=400000 for prior in selected):selected.append(xy)
    return selected

records=[]
held=[]
owners=[]
for ref in ('C485','C424','C425','C422','C421','C480','C481','C484','R410'):
    board=pcb.LoadBoard(str(current));owners.append(board);board.BuildConnectivity()
    target=pad(board,ref);rail=members(board,'C1304')
    if target.m_Uuid.AsString() in rail:continue
    splice.side=target.GetParentFootprint().GetLayer()
    width=300000 if ref=='R410' else 500000
    start=tuple(target.GetPosition())
    taps=nearby_taps(board,rail,splice.side,start,width,4800000)
    options=[]
    for xy in taps:
        path,info=splice.recover(board,[(start,xy,width,target.GetNetCode())],target.GetNetname(),None,True,True)
        if path and path[-1]==xy and info['length_mm']<=5.0:options.append((info['length_mm'],path))
    if not options:
        held.append(dict(ref=ref,nearby_taps=len(taps)))
        continue
    length,path=min(options,key=lambda o:o[0])
    for a,z in zip(path,path[1:]): board.Add(splice.wire(board,a,z,target.GetNetCode(),width))
    folder=root/'runs'/('rotated-surface-feed-'+ref);folder.mkdir(exist_ok=True)
    for cfg in ('fp-lib-table','phy-joint.kicad_pro','phy-joint.kicad_dru'):shutil.copy2(current.parent/cfg,folder/cfg)
    out=folder/current.name;pcb.ZONE_FILLER(board).Fill(board.Zones());pcb.SaveBoard(str(out),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if delta:held.append(dict(ref=ref,new_drc=delta));continue
    prior=pcb.LoadBoard(str(current));saved=pcb.LoadBoard(str(out));owners.extend([prior,saved])
    guard=verify_preservation(prior,saved)
    assert pad(saved,ref).m_Uuid.AsString() in members(saved,'C1304') and not screen(saved)
    records.append(dict(ref=ref,width_mm=width/1e6,length_mm=length,layer=saved.GetLayerName(splice.side),preserved_groups=guard['existing_connected_pad_groups_preserved']))
    meta=json.loads((current.parent/'output-legs.json').read_text());meta.update(board_sha256=digest(out),surface_feeds=records)
    (folder/'output-legs.json').write_text(json.dumps(meta,indent=2)+'\n');current=out;print(records[-1],flush=True)
(root/'rotated-surface-feeds.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],board=str(current.relative_to(root)),sha256=digest(current),records=records,held=held,assembly_ready=False),indent=2)+'\n')
print(len(records),len(held),flush=True);os._exit(0)
