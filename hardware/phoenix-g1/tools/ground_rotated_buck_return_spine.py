"""Tie the shared 0.60 mm BUCK2 return to the adjacent plane while bounding both cap-to-via paths."""
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
from pcb_power_leg import route_leg
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'rotated-buck-return-pairs.json').read_text())
old=json.loads((root/'rotated-bypass-source-mixed.json').read_text())
source=root/base['board']
digest=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
assert digest(source)==base['sha256']
assert digest(root/old['board'])==base['parent_sha256']
original=pcb.LoadBoard(str(source))
parent=pcb.LoadBoard(str(root/old['board']))
uid=lambda q:q.m_Uuid.AsString()
prior={uid(t) for t in parent.GetTracks()}
new=[t for t in original.GetTracks() if uid(t) not in prior]
assert new and all(t.GetLayer()==pcb.B_Cu and t.GetWidth()==600000 and t.GetNetname()=='GND' for t in new)
# Walk the added return in physical order for an upper bound to the farthest capacitor.
edges=[(tuple(t.GetStart()),tuple(t.GetEnd())) for t in new]
ends=[q for q in sum(([a,z] for a,z in edges),[]) if sum(q in seg for seg in edges)==1]
assert len(ends)==2
cursor=ends[0];walk=[cursor]
while edges:
    edge=next(t for t in edges if cursor in t);edges.remove(edge);cursor=next(z for z in edge if z!=cursor);walk.append(cursor)
length=sum(math.dist(a,z) for a,z in zip(walk,walk[1:]));along=0;taps=[]
for a,z in zip(walk,walk[1:]):
    seg=math.dist(a,z)
    count=math.ceil(seg/75000)
    for j in range(count):
        s=j/count;xy=tuple(round(x+(y-x)*s) for x,y in zip(a,z))
        far=max(along+seg*s,length-along-seg*s)
        budget=2400000-far
        if budget>=500000:taps.append((far,xy,budget))
    along+=seg
q=original.FindFootprintByReference('U4').FindPadByNumber('69');original.BuildConnectivity()
ground={uid(t) for t in original.GetConnectivity().GetConnectedItems(q)}
result=None;outcomes=[];owners=[original,parent]
for far,tap,budget in sorted(taps):
    board=pcb.LoadBoard(str(source));owners.append(board)
    barrels=[via for via in board.GetTracks() if isinstance(via,pcb.PCB_VIA) and uid(via) in ground and math.dist(tuple(via.GetPosition()),tap)<=budget]
    leg=route_leg(board,'GND',tap,pcb.B_Cu,tap,pcb.In4_Cu,600000,budget/1e6,shifted=True,reuse_supply_barrels=barrels)
    outcomes.append(dict(tap_nm=tap,budget_mm=budget/1e6,legal_sites=leg.get('legal_sites'),planar_reached=leg.get('source_reached')))
    if not leg['connected']:continue
    folder=root/'runs/rotated-buck2-return-spine-plane';folder.mkdir(exist_ok=True)
    for cfg in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(source.parent/cfg,folder/cfg)
    out=folder/source.name;pcb.ZONE_FILLER(board).Fill(board.Zones());pcb.SaveBoard(str(out),board)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((source.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if delta:outcomes[-1]['new_drc']=delta;continue
    saved=pcb.LoadBoard(str(out));guard=verify_preservation(original,saved)
    g=saved.FindFootprintByReference('U4').FindPadByNumber('69');members={uid(t) for t in saved.GetConnectivity().GetConnectedItems(g)}
    assert all(uid(saved.FindFootprintByReference(n).FindPadByNumber('2')) in members for n in ('C422','C432')) and not screen(saved)
    result=dict(board=str(out.relative_to(root)),sha256=digest(out),part_pair=['C422.2','C432.2'],tap_nm=tap,cap_to_tap_max_mm=far/1e6,tap_to_barrel_budget_mm=budget/1e6,leg=leg,preservation=guard)
    m=json.loads((source.parent/'output-legs.json').read_text());m.update(board_sha256=digest(out),buck2_return_spine=result);(folder/'output-legs.json').write_text(json.dumps(m,indent=2)+'\n');break
(root/'rotated-buck2-return-spine.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=result,outcomes=outcomes,assembly_ready=False),indent=2)+'\n')
print(len(taps),bool(result),flush=True);os._exit(0)
