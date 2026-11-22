"""Remove just the old MOSI tail up to the tee introduced by the recovered 1.1 V supply route."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import pcbnew as p
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen

stage=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda n:json.loads((stage/(n+'.json')).read_text())
base=read('layout-lpddr-vdd1-source');restore=read('vddq-mosi-restored');removed=read('vddq-reserved-mosi')['removed']
src=stage/restore['board'];original=stage/base['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==restore['sha256']
b=p.LoadBoard(str(src));uid=lambda item:item.m_Uuid.AsString()
items={uid(t):t for t in b.GetTracks()};newids=set(restore['records'][0]['added']);net=removed['net'];layer=b.GetLayerID(removed['layer'])
connections=[o for key,o in items.items() if key in newids and o.IsOnLayer(layer)]
anchors=[tuple(point) for t in connections for point in (t.GetStart(),t.GetEnd())]
drc=json.loads((src.parent/'drc.json').read_text())
flags=[v for v in drc['violations'] if v['type']=='track_dangling']
assert len(flags)==1
item=items[flags[0]['items'][0]['uuid']]
oldends={tuple(a) for a in removed['anchors_nm']}
start,=oldends&{tuple(item.GetStart()),tuple(item.GetEnd())}
assert item.GetNetname()==net and item.GetLayer()==layer
spent=[];records=[]
while True:
    a,z=tuple(item.GetStart()),tuple(item.GetEnd())
    end=z if start==a else a
    dx,dy=end[0]-start[0],end[1]-start[1]
    on=[xy for xy in anchors if abs((xy[0]-start[0])*dy-(xy[1]-start[1])*dx)<=max(abs(dx),abs(dy)) and min(start[0],end[0])<=xy[0]<=max(start[0],end[0]) and min(start[1],end[1])<=xy[1]<=max(start[1],end[1])]
    stop=min(on,key=lambda pt:math.dist(start,pt)) if on else None
    if stop==start:break
    spent.append(uid(item));records.append(dict(id=uid(item),start_nm=start,trim_to_nm=stop or end))
    if stop and stop!=end:
        (item.SetStart if start==a else item.SetEnd)(p.VECTOR2I(*stop))
        break
    b.Remove(item)
    if stop==end:break
    neighbours=[o for key,o in items.items() if key not in spent and key not in newids and not isinstance(o,p.PCB_VIA) and o.GetNetname()==net and o.GetLayer()==layer and end in (tuple(o.GetStart()),tuple(o.GetEnd()))]
    assert len(neighbours)==1,(end,len(neighbours))
    item=neighbours[0];start=end
folder=stage/'runs/vddq-recovered-mosi-trimmed';folder.mkdir(exist_ok=True)
for ext in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/ext,folder/ext)
out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
dr=folder/'drc.json';subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],capture_output=True,check=True)
delta=introduced(json.loads((original.parent/'drc.json').read_text()),json.loads(dr.read_text()))
saved=p.LoadBoard(str(out));saved.BuildConnectivity()
assert not delta and not screen(saved),delta
guard=verify_preservation(p.LoadBoard(str(original)),saved,replaced_copper={removed['id'],*spent})
for r,n,s,t in [('L403','2','U2','AB4'),('U1','AG19','J3','32')]:
    q=saved.FindFootprintByReference(r).FindPadByNumber(n);other=saved.FindFootprintByReference(s).FindPadByNumber(t)
    assert uid(other) in {uid(x) for x in saved.GetConnectivity().GetConnectedItems(q)}
(stage/'vddq-trimmed-mosi.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],restore_sha256=restore['sha256'],board=str(out.relative_to(stage)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),trimmed=records,replaced=sorted({removed['id'],*spent}),new_drc=delta,preservation=guard,assembly_ready=False),indent=2)+'\n')
print(len(spent),sum(math.dist(x['start_nm'],x['trim_to_nm']) for x in records)/1e6)
