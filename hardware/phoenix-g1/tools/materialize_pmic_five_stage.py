"""Materialize a floorplan on a separate native board; characterize all displaced copper."""
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from tempfile import gettempdir
import pcbnew as p
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-pmic-pwron-filter.json').read_text());src=root/meta['board']
source_geom=json.loads((Path(gettempdir())/'phoenix-pmic-floorplan-native.json').read_text())
rotated='--rotate-pmic' in sys.argv
coupled=json.loads((root/('pmic-five-stage-rotated.json' if rotated else 'pmic-five-stage-local-bank.json')).read_text())
assert hashlib.sha256(src.read_bytes()).hexdigest()==source_geom['sha256']==coupled['source_sha256']==meta['sha256']
idx=next((int(n) for n in sys.argv[1:] if n.isdecimal()),0);c=coupled['solutions'][idx];b=p.LoadBoard(str(src));b.BuildConnectivity()
poses=dict(c['rigid'])
for n,score,row in c['groups']:
    for ref,xy,angle,side,box in row:poses[ref]=[xy,angle,side]
def vec(x):return p.VECTOR2I(*[round(v*1e6) for v in x])
def rot(x,y,k):return ((x,y),(-y,x),(-x,-y),(y,-x))[k%4]
changes={}
for ref,(xy,k,face) in poses.items():
    f=b.FindFootprintByReference(ref);record=source_geom['footprints'][ref];old=record['xy'];old_layer=f.GetLayer()
    if all(abs(a-z)<1e-5 for a,z in zip(old,xy)) and not k and old_layer==(p.B_Cu if face else p.F_Cu):continue
    signal=f.FindPadByNumber('1');ox,oy=signal.GetPosition().x/1e6-old[0],signal.GetPosition().y/1e6-old[1]
    if old_layer!=(p.B_Cu if face else p.F_Cu):
        assert abs(ox)<1e-5 or abs(oy)<1e-5
        f.Flip(f.GetPosition(),p.FLIP_DIRECTION_TOP_BOTTOM if abs(ox)>abs(oy) else p.FLIP_DIRECTION_LEFT_RIGHT)
        assert math.dist((signal.GetPosition().x/1e6,signal.GetPosition().y/1e6),(old[0]+ox,old[1]+oy))<.00001
    f.Rotate(f.GetPosition(),p.EDA_ANGLE(-90*k,p.DEGREES_T));f.SetPosition(vec(xy));rx,ry=rot(ox,oy,k)
    assert math.dist((signal.GetPosition().x/1e6,signal.GetPosition().y/1e6),(xy[0]+rx,xy[1]+ry))<.00001
    changes[ref]=dict(old_xy=old,new_xy=xy,old_layer=b.GetLayerName(old_layer),new_layer=b.GetLayerName(f.GetLayer()),new_angle=f.GetOrientationDegrees())
folder=root/('runs/pmic-five-stage-rotated-'+str(idx) if rotated else 'runs/pmic-five-stage-placement-'+str(idx));folder.mkdir(exist_ok=True)
for filename in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/filename,folder/filename)
out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
drc=json.loads((folder/'drc.json').read_text());delta=introduced(json.loads((src.parent/'drc.json').read_text()),drc);saved=p.LoadBoard(str(out));saved.BuildConnectivity()
def verify_groups(ref,pin1,ref2,pin2):
    a=saved.FindFootprintByReference(ref).FindPadByNumber(pin1);z=saved.FindFootprintByReference(ref2).FindPadByNumber(pin2)
    return z.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(a)}
per_net=[]
for n,sp,ip in [(1,'12','11'),(2,'9','10'),(3,'25','24'),(4,'65','66'),(5,'53','54')]:
    per_net.append(dict(stage=n,source_to_cap=verify_groups('U4',ip,f'C42{n}','1'),switch_to_inductor=verify_groups('U4',sp,f'L40{n}','1'),inductor_to_cap=verify_groups(f'L40{n}','2',f'C43{n}','1'),input_return=verify_groups(f'C42{n}','2','U4','69'),output_return=verify_groups(f'C43{n}','2','U4','69')))
old_ids={x.m_Uuid.AsString() for x in b.GetTracks()};new_ids={x.m_Uuid.AsString() for x in saved.GetTracks()};assert old_ids==new_ids
counts=Counter();details=[]
for v in delta:
    counts[v['type']]+=v['count']
    for vr in drc['violations']:
        if v['type']==vr['type'] and set(v['items'])=={x['uuid'] for x in vr['items']}:
            details.append(dict(kind=v['type'],items=[x['description'] for x in vr['items']],uids=v['items']));break
state=dict(parent_sha256=meta['sha256'],adopted=False,board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),moves=changes,delta_counts=dict(counts),native_delta=details,stage_connectivity=per_net,mount_conflicts=screen(saved))
(folder/'placement.json').write_text(json.dumps(state,indent=2)+'\n')
print(len(changes),counts,state['mount_conflicts'],per_net,flush=True);os._exit(0)
