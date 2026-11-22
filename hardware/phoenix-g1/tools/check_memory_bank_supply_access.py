"""Test dual-barrel connections between perimeter LPDDR supply balls and the integrated bypass bank."""
import hashlib
import json
import math
import sys
import shutil
import subprocess
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
from pathlib import Path

import pcbnew as p
from pcb_power_leg import route_leg

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
inner_k1='--k1-interior' in sys.argv
perimeter='--current-perimeter' in sys.argv or inner_k1
entry=json.loads((root/('layout-memory-n12.json' if inner_k1 else 'layout-memory-trunk-widths.json' if perimeter else 'layout-ground-land-offsets.json')).read_text())
src=root/entry['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==entry['sha256']
board=p.LoadBoard(str(src))
board.BuildConnectivity()
anchor=board.FindFootprintByReference('C1666').FindPadByNumber('1')
group=board.GetConnectivity().GetConnectedItems(anchor)
if perimeter:
    member_ids={o.m_Uuid.AsString() for o in group}
    group=[o for o in [*board.GetTracks(),*(q for f in board.GetFootprints() for q in f.Pads())] if o.m_Uuid.AsString() in member_ids]
target_layer=p.In3_Cu if inner_k1 else p.B_Cu
targets=set()
for item in group:
    if not item.IsOnLayer(target_layer):continue
    if isinstance(item,p.PAD):
        targets.add(tuple(item.GetPosition()))
    elif isinstance(item,p.PCB_TRACK) and not isinstance(item,p.PCB_VIA) and item.GetWidth()>=500000:
        count=max(1,math.ceil(item.GetLength()/400000))
        for k in range(count+1):
            targets.add(tuple(round(x+(y-x)*k/count) for x,y in zip(item.GetStart(),item.GetEnd())))
follow="--reachable-ball" in sys.argv
initial=json.loads((root/"memory-bank-via-access.json").read_text()) if follow else None
rows=[]
for pad in board.FindFootprintByReference('U2').Pads():
    if pad.GetNetname()!='+1V1_LPDDR4':continue
    at=tuple(pad.GetPosition())
    distance,target=min((math.dist(at,pt),pt) for pt in targets)
    if inner_k1 and pad.GetNumber()!='K1':continue
    if perimeter and pad.GetNumber() not in ('A4','K1','K12','N12'):continue
    if distance>=(8500000 if perimeter else 3000000):continue
    if inner_k1:
        choices=sorted((math.dist(at,pt),pt) for pt in targets if math.dist(at,pt)<1400000)
        goals=[]
        for _,pt in choices:
            if all(math.dist(pt,g)>=600000 for g in goals):goals.append(pt)
        offsets=[(dx,dy,goal) for goal in goals for dx,dy in ((0,0),(100000,0),(-100000,0),(0,100000),(0,-100000))]
    elif follow:
        previous=next(row for row in initial['tested'] if row['ball']==pad.GetNumber())
        if not previous['access'].get('source_reached'):continue
        start=previous['start_nm']
        choices=sorted((math.dist(at,pt),pt) for pt in targets if math.dist(at,pt)<4500000)
        # Independent bank-entry targets, retaining both sides of bends.
        samples=[target]
        for _,pt in choices:
            if min(math.dist(pt,a) for a in samples)>=300000:samples.append(pt)
        offsets=[(start[0]-at[0],start[1]-at[1],goal) for goal in samples]
    else:
        offsets=[(dx,dy,target) for dx,dy in ((0,0),(100000,0),(-100000,0),(0,100000),(0,-100000))]
    best=None
    for dx,dy,target in offsets:
        start=at[0]+dx,at[1]+dy
        if not pad.HitTest(p.VECTOR2I(*start)):continue
        trial=p.LoadBoard(str(src))
        route=route_leg(trial,'+1V1_LPDDR4',start,p.F_Cu,target,target_layer,500000,3 if inner_k1 else 8 if perimeter else 5 if follow else 4,
                        shifted=True,allow_supply_bends=True)
        record=dict(ball=pad.GetNumber(),start_nm=start,bank_target_nm=target,access=route)
        if route['connected']:
            folder=root/'runs'/(('memory-perimeter-vias-' if perimeter else 'memory-bank-vias-')+pad.GetNumber())
            folder.mkdir(exist_ok=True)
            candidate=folder/src.name
            p.ZONE_FILLER(trial).Fill(trial.Zones())
            p.SaveBoard(str(candidate),trial)
            if perimeter:
                for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
                dr=folder/'drc.json'
                subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(candidate)],check=True,capture_output=True)
                saved=p.LoadBoard(str(candidate));saved.BuildConnectivity()
                record['new_drc']=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(dr.read_text()))
                output_pad=saved.FindFootprintByReference('U2').FindPadByNumber(pad.GetNumber())
                assert anchor.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(output_pad)}
                record['mounts']=screen(saved);record['preservation']=verify_preservation(board,saved)
            record['candidate']=str(candidate.relative_to(root))
            best=record
            break
        if best is None or (route['both_faces_reached'],route['source_reached'],route['sink_reached']) > tuple(best['access'][k] for k in ('both_faces_reached','source_reached','sink_reached')):
            best=record
    rows.append(best)
    print(pad.GetNumber(),best['access']['connected'],best['access'].get('source_reached'),flush=True)
(root/('memory-k1-inner-supply.json' if inner_k1 else 'memory-perimeter-supply-current.json' if perimeter else 'memory-bank-access-targets.json' if follow else 'memory-bank-via-access.json')).write_text(json.dumps(dict(parent_sha256=entry['sha256'],width_mm=.50,max_length_mm=3 if inner_k1 else 8 if perimeter else 5 if follow else 4,
        max_bank_projection_mm=8.5 if perimeter else 3,barrels_mm=[.45,.20],tested=rows,assembly_ready=False),indent=2)+'\n')
