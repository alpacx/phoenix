"""Evaluate actual drilled, out-of-pad exits from three PMIC service terminals."""
from pathlib import Path
import math,json,hashlib
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import barrel,make
r=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
cp=json.loads((r/'layout-soc-ground-existing-barrel.json').read_text());src=r/cp['board']
assert cp['sha256']==hashlib.sha256(src.read_bytes()).hexdigest()
b=p.LoadBoard(str(src));f=b.FindFootprintByReference('U4')
layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
objects=[*b.GetTracks(),*(q for fp in b.GetFootprints() for q in fp.Pads())]
zones=[z.Outline() for z in [*b.Zones(),*(z for fp in b.GetFootprints() for z in fp.Zones())] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
rows=[]
for pin in ('7','49','67'):
    pad=f.FindPadByNumber(pin);pos=tuple(pad.GetPosition());bbox=inflated_box(pad,4000000)
    items=[o for o in objects if bbox.Intersects(o.GetBoundingBox())]
    foreign=[(o.GetBoundingBox(),o.GetEffectiveShape(l),l) for o in items for l in layers if o.GetNetCode()!=pad.GetNetCode() and o.IsOnLayer(l)]
    front=[(bb,g) for bb,g,l in foreign if l==p.F_Cu]
    holes=[(o.GetBoundingBox(),o.GetEffectiveHoleShape()) for o in items if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    lands=[(o.GetBoundingBox(),o.GetEffectiveShape(o.GetParentFootprint().GetLayer())) for o in items if isinstance(o,p.PAD)]
    valid=[];sites=0
    for dx in range(-3000000,3000001,100000):
     for dy in range(-3000000,3000001,100000):
        if not 400000<=math.hypot(dx,dy)<=3000000:continue
        at=(pos[0]+dx,pos[1]+dy);via=barrel(b,at,pad.GetNetCode());box=inflated_box(via,300000);sh=via.GetEffectiveShape(p.F_Cu)
        if any(box.Intersects(bb) and sh.Collide(s,100000) for bb,s in lands) or any(box.Intersects(bb) and sh.Collide(s,252000) for bb,s in holes) or any(box.Intersects(bb) and sh.Collide(s,202000) for bb,s,l in foreign) or any(z.Collide(sh,0) for z in zones):continue
        sites+=1;dist=min(abs(dx),abs(dy));vx=int(math.copysign(dist,dx));vy=int(math.copysign(dist,dy))
        for mid in (pos,(pos[0]+vx,pos[1]+vy),(at[0]-vx,at[1]-vy)):
            pts=[pos]+([mid] if mid not in (pos,at) else [])+[at]
            ts=[make(b,a,z,200000,pad.GetNetCode(),p.F_Cu) for a,z in zip(pts,pts[1:])]
            if any(any(inflated_box(t,300000).Intersects(bb) and t.GetEffectiveShape(p.F_Cu).Collide(s,margin) for bb,s in obstacles) for t in ts for obstacles,margin in ((front,202000),(holes,252000))):continue
            valid.append((sum(t.GetLength() for t in ts),pts));break
    rows.append(dict(pin=pin,net=pad.GetNetname(),bare_via_sites=sites,connected_sites=len(valid),nearest=sorted(valid)[:8]))
(r/'pmic-service-layer-escape.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],cases=rows),indent=2)+'\n');print([(v['pin'],v['bare_via_sites'],v['connected_sites']) for v in rows])
