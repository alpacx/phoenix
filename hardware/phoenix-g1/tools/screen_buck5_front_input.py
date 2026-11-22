"""Evaluate a same-face bypass at the restored RK809 VCC9 toe and classify body obstructions."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import os
import pcbnew as p
from pcb_bounds import inflated_box

runs=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel/runs'
folder=runs/'pmic-five-stage-secondary-0';src=folder/'phy-joint.kicad_pcb'
meta=json.loads((folder/'output-legs.json').read_text())
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['board_sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
cap=b.FindFootprintByReference('C425');vol=cap.FindPadByNumber('1');gnd=cap.FindPadByNumber('2');side=p.F_Cu
q=b.FindFootprintByReference('U4').FindPadByNumber('54')
launch=(65000000,10575000)
assert any(isinstance(t,p.PCB_TRACK) and tuple(t.GetEnd())==launch for t in b.GetConnectivity().GetConnectedItems(q))
cap.Flip(cap.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
assert cap.GetLayer()==side and vol.GetNetname()==q.GetNetname()
vec=lambda pt:p.VECTOR2I(*pt)
items=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference()!='C425' for q in f.Pads()] if inflated_box(o,8500000).Contains(vec(launch))]
obs=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in items if o.IsOnLayer(side)]
holes=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in items if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
courts=[(f.GetReference(),f.GetCourtyard(side)) for f in b.GetFootprints() if f.GetLayer()==side and f.GetReference()!='C425' and inflated_box(f,9000000).Contains(vec(launch))]
areas=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
def clean(o):
    s=o.GetEffectiveShape(side);box=inflated_box(o,350000);code=o.GetNetCode()
    return not any(code!=c and box.Intersects(r) and s.Collide(g,202000) for c,g,r in obs) and not any(code!=c and s.Collide(h,250000) for c,h in holes) and not any(s.Collide(z,0) for z in areas)
def path(a,z,code,avoid,width):
    a,z=vec(a),vec(z);v=z-a;n=min(abs(v.x),abs(v.y));d=p.VECTOR2I(int(math.copysign(n,v.x)),int(math.copysign(n,v.y)))
    for m in (a+d,z-d):
        traces=[]
        for u,v in ((a,m),(m,z)):
            if u==v:continue
            t=p.PCB_TRACK(b);t.SetLayer(side);t.SetNetCode(code);t.SetWidth(width);t.SetStart(u);t.SetEnd(v)
            if not clean(t) or t.GetEffectiveShape(side).Collide(avoid,202000):break
            traces.append((tuple(u),tuple(v)))
        else:return traces
    return []
ep=b.FindFootprintByReference('U4').FindPadByNumber('69')
ground_ids={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(ep)}
anchors={tuple(o.GetPosition()) for o in items if o.m_Uuid.AsString() in ground_ids and (isinstance(o,p.PCB_VIA) and o.GetDrillValue()>=200000 or isinstance(o,p.PAD) and o.GetDrillSize().x>=200000)}
counts=Counter();collisions=Counter();choices=[]
for ang in (0,90,180,270):
    cap.SetOrientationDegrees(ang)
    for x in range(605,701):
        for y in range(65,153):
            xy=(x*100000,y*100000);cap.SetPosition(vec(xy));pt=tuple(vol.GetPosition())
            if math.dist(pt,launch)>3000000:continue
            counts['within_3mm']+=1;c=cap.GetCourtyard(side)
            blocks=tuple(name for name,shape in courts if c.Collide(shape,100000))
            if blocks:collisions[tuple(sorted(blocks))]+=1;continue
            counts['courtyard']+=1
            if any(c.Collide(h,50000) for _,h in holes):continue
            counts['body_and_drill']+=1
            if not clean(vol) or not clean(gnd):continue
            counts['lands']+=1
            supply=path(launch,pt,vol.GetNetCode(),gnd.GetEffectiveShape(side),500000)
            if not supply:continue
            counts['supply']+=1;gs=tuple(gnd.GetPosition());contacts=[]
            for target in sorted(anchors,key=lambda at:math.dist(gs,at)):
                if math.dist(gs,target)>3000000:break
                trace=path(gs,target,gnd.GetNetCode(),vol.GetEffectiveShape(side),500000)
                if trace:contacts.append((target,trace))
            for i,(a,first) in enumerate(contacts):
                for z,second in contacts[:i]:
                    if math.dist(a,z)>=600000:
                        choices.append(dict(xy_nm=xy,angle=ang,supply=supply,ground=[first,second]));break
                else:continue
                break
report=dict(source_sha256=meta['board_sha256'],counts=counts,body_conflicts=[(k,n) for k,n in collisions.most_common(20)],feasible=choices)
(folder/'front-input-screen.json').write_text(json.dumps(report,indent=2)+'\n')
print(counts,collisions.most_common(7),len(choices),flush=True);os._exit(0)
