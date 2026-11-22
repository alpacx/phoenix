"""Check a shortened PHY switching loop together with its neighboring CPU sense leg."""
from pathlib import Path
import json
import math
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import barrel, make, ls

root = Path(__file__).resolve().parents[1] / 'migration-rk3562/experiments/phy-power-parallel'
base = json.loads((root / 'layout-ground-copper-contact.json').read_text())
screen = json.loads((root / 'phy-boot-straps-shortened-switch.json').read_text())
assert base['sha256'] == screen['parent_sha256']
b = p.LoadBoard(str(root / base['board']))
tracks = {t.m_Uuid.AsString(): t for t in b.GetTracks()}
removed = ['0daabfe1', '4b58f10c', 'decd2621', '045e46f3', 'f1dd6464']
for prefix in removed:
    t, = [v for k,v in tracks.items() if k.startswith(prefix)]
    b.Remove(t)
f = b.FindFootprintByReference('L501')
f.SetPosition(p.VECTOR2I(*screen['best'][0]['at']))
pad = f.FindPadByNumber('1')
b.Add(make(b,(58825000,28975000),tuple(pad.GetPosition()),1550000,pad.GetNetCode(),p.F_Cu))
code = b.FindNet('VDD_CPU').GetNetCode()
a,z = (56900000,26400000),(56600000,28400000)
box = inflated_box(f,4000000)
objs = [o for o in [*b.GetTracks(),*(q for g in b.GetFootprints() for q in g.Pads())] if box.Intersects(o.GetBoundingBox())]
foil = {l:[o.GetEffectiveShape(l) for o in objs if o.IsOnLayer(l) and o.GetNetCode()!=code] for l in ls}
holes = [o.GetEffectiveHoleShape() for o in objs if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
lands = [(o.GetParentFootprint().GetLayer(),o.GetEffectiveShape(o.GetParentFootprint().GetLayer())) for o in objs if isinstance(o,p.PAD)]
def clear(o,l):
    s=o.GetEffectiveShape(l)
    return all(not s.Collide(k,202000) for k in foil[l]) and all(not s.Collide(h,252000) for h in holes)
def path(x,y,l):
    dx,dy=y[0]-x[0],y[1]-x[1];d=min(abs(dx),abs(dy))
    sx,sy=int(math.copysign(d,dx)),int(math.copysign(d,dy))
    for mid in [(x[0]+sx,x[1]+sy),(y[0]-sx,y[1]-sy)]:
        pts=[x,mid,y]
        if all(clear(make(b,u,v,200000,code,l),l) for u,v in zip(pts,pts[1:]) if u!=v):
            return pts
rows=[];sites=front=inner=0
for i in range(-20,21):
 for j in range(-20,21):
    at=(56500000+i*100000,28500000+j*100000);v=barrel(b,at,code)
    if any(not clear(v,l) for l in ls) or any(v.GetEffectiveShape(l).Collide(s,100000) for l,s in lands):continue
    sites+=1;pa=path(a,at,p.F_Cu);pz=path(z,at,p.In1_Cu)
    front+=int(bool(pa));inner+=int(bool(pz))
    if pa and pz:rows.append(dict(at=at,front=pa,inner=pz,length_mm=sum(math.dist(x,y) for pts in (pa,pz) for x,y in zip(pts,pts[1:]))/1e6))
report=dict(parent_sha256=base['sha256'],inductor_nm=screen['best'][0]['at'],cpu_removed_ids=removed[:4],sampled=1681,legal_barrels=sites,front_access=front,inner_access=inner,connected_geometries=len(rows),best=sorted(rows,key=lambda q:q['length_mm'])[:5],limits='Local octilinear branches only. No change adopted; complete strap routes and output rail require independent native DRC.')
(root/'cpu-sense-bypass-for-phy.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
