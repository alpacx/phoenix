"""Translate or rotate a bypass while retaining all original positive trace contacts and its local return."""
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_power_leg import route_leg
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'rotated-buck-return-pairs.json').read_text());current=root/base['board']
digest=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
assert digest(current)==base['sha256']
uid=lambda o:o.m_Uuid.AsString()
def pad(b,r,n):return b.FindFootprintByReference(r).FindPadByNumber(n)
def connected(b,q):return {uid(o) for o in b.GetConnectivity().GetConnectedItems(q)}
records=[];held=[];owners=[]
free_io='--move-isolated-io-cap' in sys.argv
for ref in (('C470',) if free_io else ('C431','C421','C470','C432','C422')):
    old=p.LoadBoard(str(current));owners.append(old);old.BuildConnectivity()
    f=old.FindFootprintByReference(ref);side=f.GetLayer()
    positive,ground=[f.FindPadByNumber(n) for n in ('1','2')]
    retired=set()
    if free_io:
        for q in (positive,ground):
            for t in old.GetConnectivity().GetConnectedItems(q):
                if isinstance(t,p.PAD):assert uid(t)==uid(q)
                elif isinstance(t,p.PCB_TRACK):
                    assert not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.B_Cu and all((v-q.GetPosition()).EuclideanNorm()<1500000 for v in (t.GetStart(),t.GetEnd()))
                    retired.add(uid(t))
    earth=connected(old,pad(old,'U4','69'))
    if uid(ground) in earth:continue
    centre=f.GetPosition(); original=positive.GetPosition(); angle=f.GetOrientationDegrees()
    objs=[o for o in list(old.GetTracks())+[q for fp in old.GetFootprints() if fp.GetReference()!=ref for q in fp.Pads()] if uid(o) not in retired and inflated_box(o,10500000 if free_io else 5800000).Contains(centre)]
    neighbours=[fp.GetCourtyard(side) for fp in old.GetFootprints() if fp.GetReference()!=ref and fp.GetLayer()==side and inflated_box(fp,10500000 if free_io else 4000000).Contains(centre)]
    shapes=[(o.GetNetCode(),o.GetEffectiveShape(side)) for o in objs if o.IsOnLayer(side)]
    holes=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in objs if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    required=[]
    for q in (positive,ground):
        pts=[]
        for o in objs:
            if o.GetNetCode()!=q.GetNetCode() or not isinstance(o,p.PCB_TRACK) or not o.IsOnLayer(side):continue
            for pt in {tuple(o.GetStart()),tuple(o.GetEnd())}:
                if q.HitTest(p.VECTOR2I(*pt)):pts.append(pt)
        required.append(set(pts))
    candidates=[]; bb=old.GetBoardEdgesBoundingBox()
    sourcepin=pad(old,'U4','55').GetPosition()
    window=range(-24,25) if free_io else range(-5,6)
    step=200000 if free_io else 125000
    for turn,ix,iy in itertools.product((0,90,180,270),window,window):
        if not (turn or ix or iy):continue
        f.SetOrientationDegrees(angle+turn)
        f.Move(original-positive.GetPosition()+p.VECTOR2I(ix*step,iy*step))
        if free_io and (positive.GetPosition()-sourcepin).EuclideanNorm()>(original-sourcepin).EuclideanNorm():continue
        if any(not q.HitTest(p.VECTOR2I(*pt)) for q,pts in zip((positive,ground),required) for pt in pts):continue
        court=f.GetCourtyard(side)
        if not bb.Contains(court.BBox()) or any(court.Collide(x,50000) for x in neighbours):continue
        if any(n!=q.GetNetCode() and q.GetEffectiveShape(side).Collide(sh,202000) for q in f.Pads() for n,sh in shapes):continue
        if any(n!=q.GetNetCode() and q.GetEffectiveShape(side).Collide(sh,252000) for q in f.Pads() for n,sh in holes):continue
        candidates.append((math.dist(tuple(sourcepin if free_io else original),tuple(positive.GetPosition())),angle+turn,tuple(f.GetPosition())))
    f.SetOrientationDegrees(angle);f.SetPosition(centre)
    qualified=False
    def start_board():
        board=p.LoadBoard(str(current));owners.append(board)
        for t in list(board.GetTracks()):
            if uid(t) in retired:
                board.Remove(t);owners.append(t)
        return board
    board=start_board()
    for _,orientation,pos in sorted(candidates):
        fp=board.FindFootprintByReference(ref);fp.SetOrientationDegrees(orientation);fp.SetPosition(p.VECTOR2I(*pos))
        if screen(board):continue
        g=fp.FindPadByNumber('2');at=tuple(g.GetPosition());w=300000 if ref=='C470' else 600000
        available=[v for v in board.GetTracks() if isinstance(v,p.PCB_VIA) and uid(v) in earth and math.dist(tuple(v.GetPosition()),at)<2700000]
        leg=route_leg(board,'GND',at,side,at,p.In4_Cu,w,2.4,shifted=True,reuse_supply_barrels=available)
        if not leg['connected']:continue
        folder=root/'runs'/(('rotated-io-ground-clearance-' if free_io else 'rotated-cap-ground-refit-')+ref);folder.mkdir(exist_ok=True)
        for cfg in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(current.parent/cfg,folder/cfg)
        out=folder/current.name;p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(out),board)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
        delta=introduced(json.loads((current.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
        if delta:
            board=start_board();continue
        saved=p.LoadBoard(str(out));owners.append(saved);guard=verify_preservation(old,saved,replaced_copper=retired)
        assert uid(pad(saved,ref,'2')) in connected(saved,pad(saved,'U4','69'))
        records.append(dict(ref=ref,angle=orientation,position_nm=pos,preserved_terminal_points=[len(s) for s in required],ground=leg,width_mm=w/1e6,preservation=guard))
        meta=json.loads((current.parent/'output-legs.json').read_text());meta.update(board_sha256=digest(out),refitted_bypasses=records)
        (folder/'output-legs.json').write_text(json.dumps(meta,indent=2)+'\n');current=out;qualified=True;print(ref,flush=True);break
    if not qualified:held.append(dict(ref=ref,geometric_poses=len(candidates),preserved_terminal_points=[len(g) for g in required]))
(root/('rotated-io-ground-clearance.json' if free_io else 'rotated-cap-ground-refits.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],board=str(current.relative_to(root)),sha256=digest(current),held=held,records=records,assembly_ready=False),indent=2)+'\n')
print(len(records),held,flush=True);os._exit(0)
