"""Check the straight SDA launch and through-hole window inside J3's two pad rows."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import os
import sys
import pcbnew as p
from pcb_bounds import inflated_box

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cs1='--cs1' in sys.argv
wifi='--wifi-d1' in sys.argv
base=json.loads((root/('layout-exp-spi0-pullup.json' if cs1 else 'layout-exp-sda-complete.json' if wifi else 'layout-wifi-io-pullup-bank.json')).read_text()); path=root/base['board']
assert hashlib.sha256(path.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(path))
pin=b.FindFootprintByReference('U25' if wifi else 'J3').FindPadByNumber('19' if wifi else '35' if cs1 else '23')
side=pin.GetParentFootprint().GetLayer()
pos=pin.GetPosition(); uid=lambda o:o.m_Uuid.AsString()
all_objects=list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]
nearby=[o for o in all_objects if inflated_box(o,4000000).Contains(pos) and o.GetNetCode()!=pin.GetNetCode()]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
obstacles=[(o,l,o.GetEffectiveShape(l),172000 if isinstance(o,p.PAD) and o.GetParentFootprint().GetReference()=='J3' else 202000) for o in nearby for l in layers if o.IsOnLayer(l)]
holes=[(o,o.GetEffectiveHoleShape()) for o in nearby if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
zones=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
def label(o):
    return o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.GetNetname()
trace=p.PCB_TRACK(b);trace.SetWidth(200000);trace.SetLayer(side);trace.SetNetCode(pin.GetNetCode());trace.SetStart(pos)
via=p.PCB_VIA(b);via.SetWidth(450000);via.SetDrill(200000);via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu)
ob=Counter();singletons={};launch_conflicts=Counter();isolated={};accepted=[];total=0
for y in range(pos.y+400000,pos.y+(3250000 if wifi else 2350000),25000):
    for x in range(pos.x-(1400000 if wifi else 350000),pos.x+(1400001 if wifi else 350001),25000):
        at=p.VECTOR2I(x,y);trace.SetEnd(at)
        tr=trace.GetEffectiveShape(side)
        conflicts=[o for o,l,sh,c in obstacles if l==side and tr.Collide(sh,c)]
        if conflicts:
            labels=tuple(sorted({label(o) for o in conflicts}))
            launch_conflicts[labels]+=1
            if len(labels)==1:
                group=tuple(sorted(uid(o) for o in conflicts));isolated.setdefault(group,dict(name=labels[0],point_nm=(x,y),items=group))
            continue
        total+=1;via.SetPosition(at);land=via.GetEffectiveShape(p.F_Cu);drill=via.GetEffectiveHoleShape()
        blockers=set(label(o) for o,l,sh,c in obstacles if land.Collide(sh,c) or drill.Collide(sh,252000))
        blockers.update(label(o) for o,h in holes if drill.Collide(h,252000) or land.Collide(h,252000))
        if any(z.Collide(land,0) for z in zones):blockers.add('via keepout')
        if land.Collide(pin.GetEffectiveShape(side),75000):blockers.add('source solder land')
        if len(blockers)==1:
            name=next(iter(blockers))
            if cs1 or wifi or name in ('EXP_GPIO0','EXP_GPIO1'):
                touching={uid(o):o.GetLayerName() for o,l,sh,c in obstacles if land.Collide(sh,c) or drill.Collide(sh,252000)}
                singletons.setdefault(name,[]).append(dict(point_nm=(x,y),touching=touching))
        if blockers:ob[tuple(sorted(blockers))]+=1
        else:accepted.append((x,y))
(root/('exp-cs1-launch-window.json' if cs1 else 'wifi-d1-launch-window.json' if wifi else 'exp-sda-launch-window.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],land_drill_mm=[.45,.20],width_mm=.20,isolated_track_blocks=list(isolated.values()),trace_obstacles=[dict(names=k,points=n) for k,n in sorted(launch_conflicts.items(),key=lambda pair:(len(pair[0]),-pair[1]))[:20]],single_blocker_windows=singletons,clear_launches=total,legal_via_centers_nm=accepted,blockers=[dict(obstacles=k,points=n) for k,n in sorted(ob.items(),key=lambda item:(len(item[0]),-item[1]))],assembly_ready=False),indent=2)+'\n')
print(total,len(accepted),sorted(ob.items(),key=lambda item:(len(item[0]),-item[1]))[:3],flush=True);os._exit(0)
