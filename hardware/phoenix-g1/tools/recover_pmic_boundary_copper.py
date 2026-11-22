"""Restore original external copper on the rotated coupon where complete pad contracts return."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import pcbnew as p
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
accepted=json.loads((root/'layout-pmic-pwron-filter.json').read_text())
parent=root/'runs/pmic-five-stage-c425-r410-0'
result=root/'runs/pmic-five-stage-boundary-0'
result.mkdir(exist_ok=True)
filename='phy-joint.kicad_pcb'
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):
    shutil.copy2(parent/name,result/name)
baseline=json.loads((parent/'drc.json').read_text())
old=p.LoadBoard(str(root/accepted['board']))
assert hashlib.sha256((root/accepted['board']).read_bytes()).hexdigest()==accepted['sha256']
previous=json.loads((parent/'output-legs.json').read_text())
assert hashlib.sha256((parent/filename).read_bytes()).hexdigest()==previous['board_sha256']
b=p.LoadBoard(str(parent/filename))
old_by={t.m_Uuid.AsString():t for t in old.GetTracks()}
present={t.m_Uuid.AsString() for t in b.GetTracks()}
candidates={u for u,t in old_by.items() if u not in present and t.GetNetname() in ('VDD_CPU','+5V_ADDON','PMIC_SCL','PMIC_SDA')}
copied={}
for uid in sorted(candidates):
    item=old_by[uid];old.Remove(item)
    assert item.m_Uuid.AsString()==uid
    b.Add(item)
    copied[uid]=item
def test():
    path=result/filename
    p.ZONE_FILLER(b).Fill(b.Zones())
    p.SaveBoard(str(path),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(result/'drc.json'),str(path)],check=True,capture_output=True)
    return introduced(baseline,json.loads((result/'drc.json').read_text()))
attempts=[]
while True:
    delta=test()
    failed={u for d in delta if d['type'] not in ('track_dangling','via_dangling') for u in d['items'] if u in copied}
    attempts.append(dict(tested=len(copied),blocking=delta))
    if not failed:break
    for u in failed:b.Remove(copied.pop(u))
# Keep only copper which lies in a component where at least two original pad groups rejoin.
start=p.LoadBoard(str(parent/filename));start.BuildConnectivity();b.BuildConnectivity()
def pads(board):return {q.m_Uuid.AsString():q for f in board.GetFootprints() for q in f.Pads() if q.GetNetCode()}
prior=pads(start);current=pads(b);use=set()
for u,obj in copied.items():
    contacts={q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(obj) if isinstance(q,p.PAD)}
    if len(contacts)<2:continue
    anchor=next(iter(contacts))
    former={q.m_Uuid.AsString() for q in start.GetConnectivity().GetConnectedItems(prior[anchor])}|{anchor}
    if contacts-former:use.add(u)
for u in list(copied):
    if u not in use:b.Remove(copied.pop(u))
delta=test()
previous['board_sha256']=hashlib.sha256((result/filename).read_bytes()).hexdigest()
previous['boundary_recovery']=dict(restored={u:old_by[u].GetNetname() for u in copied},introduced=delta,attempts=attempts)
(result/'output-legs.json').write_text(json.dumps(previous,indent=2)+'\n')
print(dict(initial=len(candidates),recovered=len(copied),delta=delta),flush=True);os._exit(0)
