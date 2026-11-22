"""Place each Ethernet boot strap in its signal pin's reachable surface and close the ground return."""
from pathlib import Path
from collections import defaultdict,Counter
from functools import lru_cache
import hashlib,json,math,heapq,sys
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
pmic='--pmic-local' in sys.argv
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';cp=json.loads((r/('layout-npu-c434-paired-load.json' if pmic else 'layout-ground-copper-contact.json')).read_text());src=r/cp['board'];assert cp['sha256']==hashlib.sha256(src.read_bytes()).hexdigest()
b=p.LoadBoard(str(src));b.BuildConnectivity();phy=b.FindFootprintByReference('U4' if pmic else 'U5');side=p.F_Cu;V=lambda xy:p.VECTOR2I(*xy);uid=lambda t:t.m_Uuid.AsString()
gids={uid(o) for o in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('U4').FindPadByNumber('69'))}
rows=[]
for ref,pin in ([('C415','48'),('C414','44'),('C413','46')] if pmic else [('R528','33'),('R529','34')]):
    fp=b.FindFootprintByReference(ref);source=phy.FindPadByNumber(pin);box=inflated_box(source,7000000);pin1=fp.FindPadByNumber('1');pin2=fp.FindPadByNumber('2');assert source.GetNetCode()==pin1.GetNetCode()
    if pmic and fp.GetLayer()!=side:fp.Flip(fp.GetPosition(),False)
    parts=[f for f in b.GetFootprints() if f.GetReference()!=ref]
    objs=[o for o in [*b.GetTracks(),*(q for f in parts for q in f.Pads())] if box.Intersects(o.GetBoundingBox())]
    cells=defaultdict(list);tile=500000
    def tiles(bb):return ((i,j) for i in range(bb.GetLeft()//tile,bb.GetRight()//tile+1) for j in range(bb.GetTop()//tile,bb.GetBottom()//tile+1))
    anchors=[]
    for o in objs:
        sh=o.GetEffectiveShape(side) if o.IsOnLayer(side) else None
        h=o.GetEffectiveHoleShape() if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x else None
        if sh or h:
            for c in tiles(inflated_box(o,450000)):cells[c].append((uid(o),o.GetNetCode(),sh,h))
        if uid(o) in gids and o.IsOnLayer(side):
            if isinstance(o,p.PAD) or isinstance(o,p.PCB_VIA):anchors.append(tuple(o.GetPosition()))
            else:
                a,z=tuple(o.GetStart()),tuple(o.GetEnd());n=max(1,math.ceil(o.GetLength()/250000))
                anchors.extend(tuple(round(u+(v-u)*i/n) for u,v in zip(a,z)) for i in range(n+1))
    keep=[z.Outline() for z in [*b.Zones(),*(z for f in parts for z in f.Zones())] if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
    courts=[f.GetCourtyard(side) for f in parts if f.GetLayer()==side and box.Intersects(f.GetBoundingBox())]
    def clear(o):
        sh=o.GetEffectiveShape(side);seen=set()
        for k in tiles(o.GetBoundingBox()):
            for ident,c,s,h in cells[k]:
                if ident in seen:continue
                seen.add(ident)
                if s and c!=o.GetNetCode() and sh.Collide(s,202000) or h and (c!=o.GetNetCode() or isinstance(o,p.PAD)) and sh.Collide(h,252000):return False
        return not any(z.Collide(sh,0) for z in keep)
    loc=tuple(source.GetPosition());dist={};parent={};queue=[]
    for i in range(-20,21):
     for j in range(-12,13):
        xy=(loc[0]+i*50000,loc[1]+j*50000)
        if source.GetEffectiveShape(side).Collide(V(xy),75000) and clear(make(b,xy,xy,200000,source.GetNetCode(),side)):
            dist[xy]=0;heapq.heappush(queue,(0,xy))
    while queue:
        d,a=heapq.heappop(queue)
        if dist[a]!=d:continue
        for i,j in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
            z=a[0]+i*50000,a[1]+j*50000;dd=d+math.hypot(i,j)*50000
            if dd>(2500000 if pmic else 5500000) or dd>=dist.get(z,math.inf):continue
            t=make(b,a,z,200000,source.GetNetCode(),side)
            if clear(t):dist[z]=dd;parent[z]=a;heapq.heappush(queue,(dd,z))
    ops=[];stats=Counter()
    for angle in (0,90,180,270):
        fp.SetOrientationDegrees(angle);fp.SetPosition(V((0,0)));offset=tuple(pin1.GetPosition())
        for at in sorted(dist,key=dist.get):
            if any(n%100000 for n in at):continue
            pos=(at[0]-offset[0],at[1]-offset[1]);fp.SetPosition(V(pos))
            if any(fp.GetCourtyard(side).Collide(z,100000) for z in courts):continue
            stats['courtyard']+=1
            if not clear(pin1) or not clear(pin2):continue
            stats['pads']+=1;gxy=tuple(pin2.GetPosition())
            for ground in sorted(anchors,key=lambda q:math.dist(q,gxy)):
                if math.dist(ground,gxy)>(1200000 if pmic else 2200000):break
                wire=make(b,gxy,ground,300000 if pmic else 250000,pin2.GetNetCode(),side)
                if not clear(wire) or wire.GetEffectiveShape(side).Collide(pin1.GetEffectiveShape(side),202000):continue
                points=[at]
                while points[-1] in parent:points.append(parent[points[-1]])
                points.reverse()
                if any(make(b,u,v,200000,source.GetNetCode(),side).GetEffectiveShape(side).Collide(pin2.GetEffectiveShape(side),202000) or make(b,u,v,200000,source.GetNetCode(),side).GetEffectiveShape(side).Collide(wire.GetEffectiveShape(side),202000) for u,v in zip(points,points[1:])):continue
                ops.append(dict(center=pos,angle=angle,signal_nm=points,ground_nm=[gxy,ground],total_mm=(dist[at]+math.dist(gxy,ground))/1e6));break
    toe=(max if pmic else min)(dist,key=lambda xy:xy[0]) if dist else (loc[0]+420000,loc[1]) if pmic else loc
    lead=make(b,toe,(toe[0]+(1200000 if pmic else -1200000),toe[1]),200000,source.GetNetCode(),side)
    hit=[]
    for obj in objs:
        if obj.GetNetCode()==source.GetNetCode() or not obj.IsOnLayer(side):continue
        if lead.GetEffectiveShape(side).Collide(obj.GetEffectiveShape(side),202000):
            hit.append((obj.GetNetname(),obj.GetParentFootprint().GetReference()+'.'+obj.GetNumber() if isinstance(obj,p.PAD) else uid(obj)))
    rows.append(dict(ref=ref,pin=pin,**({'east_toe_nm':toe,'east_blockers':hit} if pmic else {'west_toe_nm':toe,'west_blockers':hit}),launches=sum(cost==0 for cost in dist.values()),reachable=len(dist),stats=dict(stats),best=sorted(ops,key=lambda v:v['total_mm'])[:5]))
    # Reset pose for the next resistor's fixed-obstacle inventory.
    src_board=p.LoadBoard(str(src));src_fp=src_board.FindFootprintByReference(ref);fp.SetPosition(src_fp.GetPosition());fp.SetOrientationDegrees(src_fp.GetOrientationDegrees())
(r/('pmic-three-local-bypass-front.json' if pmic else 'phy-ldo-strap-surface-and-return.json')).write_text(json.dumps(dict(parent_sha256=cp['sha256'],rows=rows),indent=2)+'\n');print([(v['ref'],v['launches'],v['reachable'],v['stats'],len(v['best'])) for v in rows])
