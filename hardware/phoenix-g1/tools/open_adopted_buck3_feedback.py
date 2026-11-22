"""Recover the FB3 escape by preserving conductance and terminal contacts on the obstructing input rail."""
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

import pcbnew as pcb
from drc_regression import introduced
from native_front_splice import compact
from pcb_bounds import inflated_box
from pcb_power_leg import make,barrel
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'layout-usb-direction-complete.json').read_text());src=root/base['board']
window=json.loads((root/'adopted-buck3-feedback-windows.json').read_text())
digest=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
assert digest(src)==base['sha256']==window['coupon_sha256']
routes=[(uid,entry) for row in window['circuits'] for uid,blocker in row['single_copper_blockers'].items() for entry in blocker['sites']]
assert len({uid for uid,_ in routes})==1
original=pcb.LoadBoard(str(src));b=pcb.LoadBoard(str(src));uid=lambda o:o.m_Uuid.AsString()
old=next(o for o in b.GetTracks() if uid(o)==routes[0][0]);layer=old.GetLayer();code=old.GetNetCode();a,z=tuple(old.GetStart()),tuple(old.GetEnd())
assert layer==pcb.In4_Cu and old.GetNetname()=='+3V3_SYS' and old.GetWidth()==600000 and a[1]==z[1]
if a[0]>z[0]:a,z=z,a
old_squares=old.GetLength()/old.GetWidth();q=b.FindFootprintByReference('U4').FindPadByNumber('27');b.Remove(old)
near=[o for o in [*list(b.GetTracks()),*(q for f in b.GetFootprints() for q in f.Pads())] if inflated_box(o,6700000).Contains(pcb.VECTOR2I(*a))]
shapes=[(o.GetEffectiveShape(layer),o.GetBoundingBox()) for o in near if o.IsOnLayer(layer) and o.GetNetCode()!=code]
holes=[(o.GetEffectiveHoleShape(),o.GetBoundingBox()) for o in near if o.GetNetCode()!=code and (isinstance(o,pcb.PCB_VIA) or isinstance(o,pcb.PAD) and o.GetDrillSize().x)]
for area in [*list(b.Zones()),*(s for f in b.GetFootprints() for s in f.Zones())]:
    if area.GetIsRuleArea() and area.IsOnLayer(layer) and area.GetDoNotAllowTracks():shapes.append((area.Outline(),area.GetBoundingBox()))
# Widening this power conductor must not project a fresh slot below a controlled top/bottom signal.
fast_prefix=('LPDDR4_', 'USB_TX','USB_RX','USB_DP','USB_DM','ADDON_USB','MUX_TX','ETH_MDI','WIFI_RF')
fast=[o.GetEffectiveShape(pcb.B_Cu) for o in near if o.IsOnLayer(pcb.B_Cu) and o.GetNetname().startswith(fast_prefix)]
check=lambda shape,entries,margin,box:all(not box.Intersects(bb) or not shape.Collide(sh,margin) for sh,bb in entries)
cache={}
def segment(x,y,width):
    key=(x,y,width)
    if key not in cache:
        t=make(b,x,y,width,code,layer);s=t.GetEffectiveShape(layer);bb=inflated_box(t,450000)
        cache[key]=t if check(s,shapes,202000,bb) and check(s,holes,252000,bb) and not any(s.Collide(sh,350000) for sh in fast) else None
    return cache[key]
proposals=[];tested=dict(square=0,free=0,via=0)
for offset in (650000,750000,850000,950000,1050000,1200000):
 for sign,width in itertools.product((-1,1),(650000,700000,750000,800000,850000,900000)):
    level=a[1]+sign*offset
    for rise,fall in itertools.product((offset,offset*3//4,offset//2,offset//4,0),repeat=2):
        for pre,post in itertools.product((0,250000,500000,750000,1000000),(0,150000,300000)):
            x1=a[0]+pre;x2=z[0]-post
            if x2-fall<x1+rise:continue
            points=[a,(x1,a[1]),(x1+rise,level),(x2-fall,level),(x2,z[1]),z]
            pts=[points[0]]
            for xy in points[1:]:
                if xy!=pts[-1]:pts.append(xy)
            length=sum(math.dist(x,y) for x,y in zip(pts,pts[1:]))
            if length/width>old_squares:continue
            tested['square']+=1
            parts=[segment(x,y,width) for x,y in zip(pts,pts[1:])]
            if any(s is None for s in parts):continue
            tested['free']+=1
            for _,entry in routes:
                pos=tuple(entry['via_nm']);via=barrel(b,pos,q.GetNetCode());ann=via.GetEffectiveShape(layer);drill=via.GetEffectiveHoleShape()
                if any(s.GetEffectiveShape(layer).Collide(ann,202000) or s.GetEffectiveShape(layer).Collide(drill,252000) for s in parts):continue
                tested['via']+=1
                proposals.append((length-width*.25+entry['length_mm']*1e5,length/width,pts,width,entry))
folder=root/'runs/adopted-buck3-feedback-supply-relief';folder.mkdir(exist_ok=True)
for cfg in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/cfg,folder/cfg)
winner=None;rejected=[]
for _,n_squares,pts,width,entry in sorted(proposals,key=lambda row:row[0])[:35]:
    parts=[make(b,x,y,width,code,layer) for x,y in zip(pts,pts[1:])]
    launch=compact([tuple(i) for i in entry['launch_nm']]);via=barrel(b,launch[-1],q.GetNetCode())
    added=parts+[make(b,x,y,200000,q.GetNetCode(),pcb.F_Cu) for x,y in zip(launch,launch[1:]) if x!=y]+[via]
    for o in added:b.Add(o)
    out=folder/src.name;pcb.ZONE_FILLER(b).Fill(b.Zones());pcb.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if all(v['type']=='via_dangling' and v['items']==[uid(via)] for v in delta):
        saved=pcb.LoadBoard(str(out))
        try:guard=verify_preservation(original,saved,replaced_copper=[uid(old)])
        except AssertionError as e:rejected.append(str(e));guard=None
        if guard:
            assert uid(via) in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('U4').FindPadByNumber('27'))}
            winner=dict(board=str(out.relative_to(root)),sha256=digest(out),supply_width_mm=width/1e6,old_squares=old_squares,new_squares=n_squares,original_uuid=uid(old),via_nm=entry['via_nm'],via_uuid=uid(via),new_drc=delta,preservation=guard)
            break
    else:rejected.append(delta)
    for o in added:b.Remove(o)
(root/'adopted-buck3-feedback-relief.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],screen=tested,candidate=winner,rejected=rejected,assembly_ready=False),indent=2)+'\n')
print(tested,bool(winner),len(rejected),flush=True);os._exit(0)
