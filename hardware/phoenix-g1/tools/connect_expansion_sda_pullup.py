"""Place the SDA pull-up at J3's new via and restore its 3.3 V connection on the back."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import math
import os
import sys
import shutil
import subprocess
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def read(n):return json.loads((root/(n+'.json')).read_text())
spi_trial='--spi0-signal' in sys.argv
spi='--spi0' in sys.argv or spi_trial
wifi_soc='--wifi-d1-soc' in sys.argv
wifi='--wifi-d1' in sys.argv or wifi_soc
base=read('layout-command-ca1' if wifi_soc else 'layout-exp-sda-complete' if wifi or spi else 'layout-wifi-io-pullup-bank')
cp=base if spi or wifi else read('exp-sda-gpio1-launch')['candidate']
target_ref,target_pin=('U1','AG17') if spi else ('U1','V25') if wifi_soc else ('U25','19') if wifi else ('J3','23')
res_ref='R2103' if spi else 'R2011' if wifi else 'R2101'
src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();side=p.F_Cu if wifi_soc else p.B_Cu;v=lambda xy:p.VECTOR2I(*xy);uid=lambda o:o.m_Uuid.AsString()
power_ref,power_pin=('TP5','1') if spi else ('U4','55')
ref=b.FindFootprintByReference(res_ref);g=b.FindFootprintByReference(power_ref).FindPadByNumber(power_pin)
rail={uid(o) for o in b.GetConnectivity().GetConnectedItems(g)}
from collections import defaultdict
def stub_chain(b,ref,seed):
    objs=[o for o in b.GetTracks() if o.GetNetCode()==ref.GetNetCode()]
    idx=defaultdict(list)
    for o in objs:
        if isinstance(o,p.PCB_VIA):
            for l in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:idx[(l,tuple(o.GetPosition()))].append(o)
        else:
            for pt in (o.GetStart(),o.GetEnd()):idx[o.GetLayer(),tuple(pt)].append(o)
    ids=set();cur=next(o for o in objs if o.m_Uuid.AsString()==seed)
    while True:
        ids.add(cur.m_Uuid.AsString())
        keys=[(l,tuple(cur.GetPosition())) for l in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]] if isinstance(cur,p.PCB_VIA) else [(cur.GetLayer(),tuple(q)) for q in [cur.GetStart(),cur.GetEnd()]]
        if any(q.GetNetCode()==ref.GetNetCode() and q.m_Uuid.AsString()!=ref.m_Uuid.AsString() and q.IsOnLayer(l) and q.HitTest(p.VECTOR2I(*pt)) for f in b.GetFootprints() for q in f.Pads() for l,pt in keys):break
        more={o.m_Uuid.AsString():o for k in keys for o in idx[k] if o.m_Uuid.AsString() not in ids}
        if len(more)!=1:break
        cur=next(iter(more.values()))
    return ids

remove=set() if wifi else stub_chain(b,ref.FindPadByNumber('2'),'7747724e-cd79-4819-bf31-6616e58beed0') if spi else set(read('exp-data-pullup-feed')['records'][0]['added']);assert spi or len(remove)==(0 if wifi else 1)
original_tracks=list(b.GetTracks())
for o in original_tracks:
    if uid(o) in remove:b.Remove(o)
if ref.GetLayer()!=side:ref.Flip(ref.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
one=ref.FindPadByNumber('1');two=ref.FindPadByNumber('2');at=tuple(b.FindFootprintByReference(target_ref).FindPadByNumber(target_pin).GetPosition()) if wifi else (46300000,27200000) if spi else tuple(cp['site_nm'])
allobs=list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference()!=res_ref for q in f.Pads()]
near=[o for o in allobs if inflated_box(o,10000000).Contains(v(at))]
shapes=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in near if o.IsOnLayer(side)]
holes=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
courts=[f.GetCourtyard(side) for f in b.GetFootprints() if f.GetReference()!=res_ref and f.GetLayer()==side and inflated_box(f,9500000).Contains(v(at))]
zones=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
targets=set()
for o in near:
 if uid(o) not in rail or not o.IsOnLayer(side):continue
 if isinstance(o,p.PAD):targets.add(tuple(o.GetPosition()))
 else:targets.update((tuple(o.GetStart()),tuple(o.GetEnd())))
def clean(o):
    sh=o.GetEffectiveShape(side);bb=inflated_box(o,350000);nc=o.GetNetCode()
    return all(nc==c or not bb.Intersects(box) or not sh.Collide(s,202000) for c,s,box in shapes) and all(nc==c or not sh.Collide(h,252000) for c,h in holes) and all(not sh.Collide(z,0) for z in zones)
def paths(q,z,width,other):
    a=tuple(q.GetPosition());dx=z[0]-a[0];dy=z[1]-a[1];d=min(abs(dx),abs(dy));i=int(math.copysign(d,dx));j=int(math.copysign(d,dy))
    for c in ((a[0]+i,a[1]+j),(z[0]-i,z[1]-j)):
        ts=[]
        for start,end in zip((a,c),(c,z)):
            if start==end:continue
            t=p.PCB_TRACK(b);t.SetStart(v(start));t.SetEnd(v(end));t.SetWidth(width);t.SetLayer(side);t.SetNetCode(q.GetNetCode())
            if not clean(t) or any(t.GetEffectiveShape(side).Collide(k.GetEffectiveShape(side),202000) for k in other):break
            ts.append(t)
        else:yield ts
folder=root/('runs/spi0-local-signal' if spi_trial else 'runs/spi0-dual-land' if spi else 'runs/wifi-d1-soc-dual-land' if wifi_soc else 'runs/wifi-d1-dual-land' if wifi else 'runs/exp-sda-dual-land');folder.mkdir(exist_ok=True);out=folder/src.name
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
counts=Counter();rejections=[];winner=None
offsets=sorted(((x,y) for x in range(-42 if wifi else -30,43 if wifi else 31) for y in range(-20 if wifi else -9,49 if wifi else 41)),key=lambda k:math.hypot(*k))
def candidates():
    for x,y in offsets:
      for ang in (0,90,180,270):
        pos=(at[0]+x*100000,at[1]+y*100000);ref.SetPosition(v(pos));ref.SetOrientationDegrees(ang);court=ref.GetCourtyard(side)
        if court.BBox().GetTop()<500000 or any(court.Collide(c,100000) for c in courts) or not all(clean(q) for q in (one,two)):continue
        signal=[ts for ts in paths(one,at,200000,[two]) if ts and sum(t.GetLength() for t in ts)<=3500000]
        if not signal:continue
        counts['signal_poses']+=1
        if spi_trial:
            yield pos,ang,None,signal[0]
            continue
        for z in sorted(targets,key=lambda z:math.dist(z,tuple(two.GetPosition()))):
            if math.dist(z,tuple(two.GetPosition()))>(11500000 if spi else 8200000):break
            for ts in signal:
                for pw in paths(two,z,250000,[one]+ts):
                    yield pos,ang,z,ts+pw
for pos,ang,z,items in candidates():
    for t in items:b.Add(t)
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads(((root/base['board']).parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if not delta:
        saved=p.LoadBoard(str(out));saved.BuildConnectivity();r=saved.FindFootprintByReference(res_ref)
        def joined(a,ref,num):
            return uid(saved.FindFootprintByReference(ref).FindPadByNumber(num)) in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(a)}
        if joined(r.FindPadByNumber('1'),target_ref,target_pin) and (spi_trial or joined(r.FindPadByNumber('2'),power_ref,power_pin)) and not screen(saved):
            replaced=set() if wifi else remove if spi else remove|set(cp['preservation']['explicitly_replaced_copper']);proof=verify_preservation(p.LoadBoard(str(root/base['board'])),saved,removed_refs=[res_ref] if spi_trial else [],replaced_copper=replaced)
            winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),preservation=proof,new_drc=delta,center_nm=pos,angle=ang,rail_pickup_nm=z);break
    for t in items:b.Remove(t)
    rejections.append(dict(pose=pos,angle=ang,delta=delta))
    if len(rejections)>=20:break
(root/('spi0-local-signal.json' if spi_trial else 'spi0-dual-land.json' if spi else 'wifi-d1-soc-dual-land.json' if wifi_soc else 'wifi-d1-dual-land.json' if wifi else 'exp-sda-dual-land.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=winner,counts=counts,attempts=rejections,assembly_ready=False),indent=2)+'\n')
print(bool(winner),counts,len(rejections),len(targets),flush=True);os._exit(0)
