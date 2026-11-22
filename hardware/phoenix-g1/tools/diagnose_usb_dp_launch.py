"""Find the individual front-copper objects closing the A/B USB2 D+ contact launch."""
from pathlib import Path
from collections import Counter,deque,defaultdict
from functools import lru_cache
import hashlib,json,math
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make,ls,barrel
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';base=json.loads((r/'layout-npu-c434-paired-load.json').read_text());src=r/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));j=b.FindFootprintByReference('J1');q=j.FindPadByNumber('B6');goal=j.FindPadByNumber('A6');start=tuple(q.GetPosition());code=q.GetNetCode();fc=p.F_Cu;V=lambda at:p.VECTOR2I(*at)
box=inflated_box(q,4000000);objects=[o for o in [*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())] if box.Intersects(o.GetBoundingBox())]
labels={o.m_Uuid.AsString():dict(net=o.GetNetname(),kind=o.GetClass(),label=o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else None) for o in objects}
foil={l:[(o.m_Uuid.AsString(),o.GetEffectiveShape(l),o.GetBoundingBox()) for o in objects if o.GetNetCode()!=code and o.IsOnLayer(l)] for l in ls}
holes=[(o.m_Uuid.AsString(),o.GetEffectiveHoleShape(),o.GetPosition()) for o in objects if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
lands=[(o.m_Uuid.AsString(),o.GetEffectiveShape(o.GetParentFootprint().GetLayer()),o.GetBoundingBox()) for o in objects if isinstance(o,p.PAD)]
zones=[z for z in [*b.Zones(),*(z for f in b.GetFootprints() for z in f.Zones())] if z.IsRuleArea()] if hasattr(p.ZONE,'IsRuleArea') else [z for z in [*b.Zones(),*(z for f in b.GetFootprints() for z in f.Zones())] if z.GetIsRuleArea()]
for z in zones:labels[z.m_Uuid.AsString()]=dict(kind='ZONE',label=z.GetZoneName(),net='')
@lru_cache(None)
def barriers(a,z,via=False):
    item=barrel(b,a,code) if via else make(b,a,z,200000,code,fc);bb=inflated_box(item,405000);sh=item.GetEffectiveShape(fc);hits={key for key,h,xy in holes if bb.Contains(xy) and sh.Collide(h,252000)}
    for l in (ls if via else (fc,)):
        field=item.GetEffectiveShape(l)
        for key,s,bounds in foil[l]:
            if bb.Intersects(bounds) and (field.Collide(s,202000) or via and item.GetEffectiveHoleShape().Collide(s,252000)):hits.add(key)
    if via:hits.update(key for key,s,bounds in lands if bb.Intersects(bounds) and sh.Collide(s,100000))
    hits.update(v.m_Uuid.AsString() for v in zones if (v.GetDoNotAllowVias() if via else v.IsOnLayer(fc) and v.GetDoNotAllowTracks()) and sh.Collide(v.Outline(),0))
    return frozenset(hits)
def walk(skip=frozenset()):
    seeds={(start[0]+i*50000,start[1]+j*50000) for i in range(-7,8) for j in range(-3,4)}
    seen={at for at in seeds if q.GetEffectiveShape(fc).Collide(V(at),0) and not barriers(at,at)-skip};queue=deque(seen);blocked=Counter();sites=[];hits_target=False
    while queue:
        at=queue.popleft()
        if not barriers(at,at,True)-skip:sites.append(at)
        if goal.GetEffectiveShape(fc).Collide(V(at),0):hits_target=True
        for i,jj in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]:
            z=at[0]+i*50000,at[1]+jj*50000
            if z in seen or math.dist(start,z)>2400000:continue
            blockers=barriers(at,z)-skip
            if blockers:
                if len(blockers)==1:blocked.update(blockers)
            else:seen.add(z);queue.append(z)
    return dict(nodes=len(seen),max_displacement_mm=max(math.dist(start,at) for at in seen)/1e6 if seen else 0,via_sites=len(sites),touch_A6=hits_target),blocked
fixed,cut=walk();tests=[]
for key,count in cut.most_common():
    info=labels[key];row=dict(id=key,**info,unique_blocked_edges=count)
    if info['kind'] in ('PCB_TRACK','PCB_VIA'):row['with_object_removed']=walk(frozenset([key]))[0]
    tests.append(row)
(r/'usb-dp-b6-physical-barriers.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],base=fixed,individual=tests),indent=2)+'\n');print(fixed,tests)
