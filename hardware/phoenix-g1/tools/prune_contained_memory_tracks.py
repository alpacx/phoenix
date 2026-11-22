"""Remove only wholly redundant new AB4 copper represented by overlapping native segments."""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import math
import shutil
import subprocess
import sys

import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda name:json.loads((root/(name+'.json')).read_text())
source_name='layout-memory-ab4-bypass' if len(sys.argv)==1 else sys.argv[1]
base=read('layout-ground-land-offsets');data=read(source_name);source=data.get('candidate',data)
def load(row):
    path=root/row['board']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    return p.LoadBoard(str(path))
before=load(base);original=load(source);changed=load(source)
old={t.m_Uuid.AsString() for t in before.GetTracks()}
groups=defaultdict(list)
for tr in changed.GetTracks():
    if tr.m_Uuid.AsString() in old or isinstance(tr,p.PCB_VIA):continue
    x,y=tuple(tr.GetStart());u,v=tuple(tr.GetEnd());dx,dy=u-x,v-y
    divisor=math.gcd(abs(dx),abs(dy))
    if not divisor:continue
    dx//=divisor;dy//=divisor
    if dx<0 or dx==0 and dy<0:dx=-dx;dy=-dy
    key=tr.GetNetname(),tr.GetLayer(),tr.GetWidth(),dx,dy,dy*x-dx*y
    low,high=sorted((dx*x+dy*y,dx*u+dy*v))
    groups[key].append((high-low,low,high,tr.m_Uuid.AsString(),tr))
removed={}
for entries in groups.values():
    keep=[]
    for length,low,high,uid,track in sorted(entries,reverse=True,key=lambda row:row[:4]):
        covering=next((k for start,end,k in keep if start<=low and high<=end),None)
        if covering:
            removed[uid]=covering;changed.Remove(track)
        else:
            keep.append((low,high,uid))
folder=root/'runs/memory-ab4-normalized';folder.mkdir(exist_ok=True)
src=root/source['board'];out=folder/src.name
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):
    shutil.copy2(src.parent/name,folder/name)
p.ZONE_FILLER(changed).Fill(changed.Zones());p.SaveBoard(str(out),changed)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
report=lambda f:json.loads((f/'drc.json').read_text())
diff=introduced(report(src.parent),report(folder));saved=p.LoadBoard(str(out))
preserved=verify_preservation(original,saved,replaced_copper=removed)
result=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),parent_sha256=source['sha256'],
            wholly_contained_tracks=removed,preservation=preserved,new_drc=diff,mounts=screen(saved),assembly_ready=False)
(root/'memory-ab4-normalized.json').write_text(json.dumps(result,indent=2)+'\n')
print(len(removed),diff,flush=True)
