"""Find octilinear, ground-referenced source branches at actual lands of fixed RGMII resistors."""
from pathlib import Path
from collections import defaultdict
from functools import lru_cache
import heapq,hashlib,json,math,sys
import pcbnew as p
from pcb_power_leg import make
from pcb_bounds import inflated_box
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';base=json.loads((r/'layout-rgmii-short-source-clock.json').read_text());src=r/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();V=lambda xy:p.VECTOR2I(*xy);s=p.F_Cu;grid=50000
polys=[z.GetFilledPolysList(p.In1_Cu) for z in b.Zones() if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(p.In1_Cu)];rows=[]
exact='--exact-phy' in sys.argv
move='--relocate' in sys.argv
for n in range(501,513):
    f=b.FindFootprintByReference('R'+str(n));source=b.FindFootprintByReference('U1' if n<=506 else 'U5');pr=f.FindPadByNumber('1' if n<=506 else '2');q=next(q for q in source.Pads() if q.GetNetCode()==pr.GetNetCode())
    if (not move and f.GetLayer()!=s) or pr.m_Uuid.AsString() in {i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(q)}:continue
    if move:
        if any(b.GetConnectivity().GetConnectedTracks(land) for land in f.Pads()):continue
        if f.GetLayer()!=s:f.Flip(f.GetPosition(),False)
    box=inflated_box(q,10500000);obj=[o for o in [*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())] if (not move or not isinstance(o,p.PAD) or o.GetParentFootprint().GetReference()!=f.GetReference()) and o.GetNetCode()!=q.GetNetCode() and box.Intersects(o.GetBoundingBox())];tiles=defaultdict(list)
    for o in obj:
        sh=o.GetEffectiveShape(s) if o.IsOnLayer(s) else None;h=o.GetEffectiveHoleShape() if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x else None
        if not sh and not h:continue
        noise=o.GetNetname().startswith(('PMIC_SW','CPU_SW','PHY_SW','WIFI_SW'));bb=inflated_box(o,1500000 if noise else 500000)
        for i in range(bb.GetLeft()//500000,bb.GetRight()//500000+1):
         for j in range(bb.GetTop()//500000,bb.GetBottom()//500000+1):tiles[i,j].append((sh,h,noise))
    g=[z.Outline() for z in [*b.Zones(),*(z for f in b.GetFootprints() for z in f.Zones())] if z.GetIsRuleArea() and z.IsOnLayer(s) and z.GetDoNotAllowTracks()]
    trace=make(b,(0,0),(0,0),200000,q.GetNetCode(),s)
    @lru_cache(None)
    def reference(xy):return any(h.Contains(V(xy)) for h in polys)
    @lru_cache(None)
    def clear(a,z):
        trace.SetStart(V(a));trace.SetEnd(V(z));sh=trace.GetEffectiveShape(s)
        if any((k and sh.Collide(k,1000000 if noise else 202000)) or (h and sh.Collide(h,252000)) for k,h,noise in tiles[a[0]//500000,a[1]//500000]) or any(sh.Collide(k,0) for k in g):return False
        dx=z[0]-a[0];dy=z[1]-a[1];ll=math.hypot(dx,dy)
        if not ll:return reference(a)
        for i in (0,.5,1):
         for o in (-110000,0,110000):
            if not reference((round(a[0]+i*dx-o*dy/ll),round(a[1]+i*dy+o*dx/ll))):return False
        return True
    def on_land(pad):
        sh=pad.GetEffectiveShape(s);bb=inflated_box(pad,75000)
        return {(x*grid,y*grid) for x in range(bb.GetLeft()//grid,bb.GetRight()//grid+1) for y in range(bb.GetTop()//grid,bb.GetBottom()//grid+1) if sh.Collide(V((x*grid,y*grid)),50000) and clear((x*grid,y*grid),(x*grid,y*grid))}
    starts=on_land(q);ends=on_land(pr);cost={at:0 for at in starts};prev={};precise={}
    if exact and n>506:
        toe_doc=json.loads((r/'rgmii-phy-exact-outer-toes.json').read_text());assert toe_doc['parent_sha256']==base['sha256']
        rr=next((v for v in toe_doc['rows'] if v['pin']==q.GetNumber()),None)
        for raw in (rr['examples'] if rr else []):
            start=tuple(raw);tip=(start[0]+rr['direction'][0]*300000,start[1]+rr['direction'][1]*300000)
            for sx in (tip[0]//grid*grid,tip[0]//grid*grid+grid):
             for sy in (tip[1]//grid*grid,tip[1]//grid*grid+grid):
                snapped=(sx,sy)
                if clear(start,tip) and clear(tip,snapped):
                    dd=math.dist(start,tip)+math.dist(tip,snapped)
                    if dd<cost.get(snapped,math.inf):cost[snapped]=dd;precise[snapped]=[start,tip];starts.add(snapped)
    queue=[(dd,at) for at,dd in cost.items()];heapq.heapify(queue);result=None
    while queue:
        d,a=heapq.heappop(queue)
        if cost[a]!=d:continue
        if not move and a in ends:
            path=[a]
            while path[-1] in prev:path.append(prev[path[-1]])
            result=dict(length_mm=d/1e6,path_nm=precise.get(path[-1],[])+path[::-1]);break
        for i,j in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
            z=a[0]+i*grid,a[1]+j*grid;dd=d+math.hypot(i,j)*grid
            if dd>(3200000 if move else 7000000) or dd>=cost.get(z,math.inf) or not clear(a,z):continue
            cost[z]=dd;prev[z]=a;heapq.heappush(queue,(dd,z))
    candidates=[]
    if move and cost:
        osc=[ff.GetCourtyard(s) for ff in b.GetFootprints() if ff.GetLayer()==s and ff.GetReference()!=f.GetReference() and box.Intersects(ff.GetBoundingBox())]
        copper=[(o.GetNetCode(),o.GetEffectiveShape(s),o.GetBoundingBox()) for o in [*b.GetTracks(),*(land for ff in b.GetFootprints() if ff.GetReference()!=f.GetReference() for land in ff.Pads())] if o.IsOnLayer(s) and box.Intersects(o.GetBoundingBox())]
        via_shapes=[(o.GetEffectiveShape(s),o.GetBoundingBox()) for o in b.GetTracks() if isinstance(o,p.PCB_VIA) and box.Intersects(o.GetBoundingBox())]
        seen=set();qa=f.FindPadByNumber('2' if n<=506 else '1')
        for pt in sorted(cost,key=cost.get):
            if not cost[pt] or any(x%100000 for x in pt):continue
            for an in (0,90,180,270):
             f.SetOrientationDegrees(an);f.SetPosition(V((0,0)));offset=tuple(pr.GetPosition())
             for i,j in ((0,0),(1,0),(-1,0),(0,1),(0,-1),(2,0),(-2,0),(0,2),(0,-2)):
                xy=(pt[0]-offset[0]+i*100000,pt[1]-offset[1]+j*100000)
                if (xy,an) in seen:continue
                seen.add((xy,an));f.SetPosition(V(xy))
                if not pr.HitTest(V(pt)) or any(f.GetCourtyard(s).Collide(c,100000) for c in osc):continue
                if any(land.GetEffectiveShape(s).Collide(shape,202000) for land in f.Pads() for co,shape,bb in copper if co!=land.GetNetCode() and inflated_box(land,450000).Intersects(bb)):continue
                if any(land.GetEffectiveShape(s).Collide(shape,100000) for land in f.Pads() for shape,bb in via_shapes if inflated_box(land,200000).Intersects(bb)):continue
                path=[pt]
                while path[-1] in prev:path.append(prev[path[-1]])
                path=precise.get(path[-1],[])+path[::-1]
                if any(make(b,a,z,200000,q.GetNetCode(),s).GetEffectiveShape(s).Collide(qa.GetEffectiveShape(s),202000) for a,z in zip(path,path[1:])):continue
                candidates.append(dict(at=xy,angle=an,length_mm=cost[pt]/1e6,path_nm=path))
        raw=p.LoadBoard(str(src));orig=raw.FindFootprintByReference(f.GetReference())
        if orig.GetLayer()!=f.GetLayer():f.Flip(f.GetPosition(),False)
        f.SetOrientationDegrees(orig.GetOrientationDegrees());f.SetPosition(orig.GetPosition())
    rows.append(dict(ref=f.GetReference(),pin=q.GetNumber(),net=q.GetNetname(),source_toes=len(starts),resistor_toes=len(ends),states=len(cost),result=result,candidates=candidates[:4]))
(r/('rgmii-exact-toe-sliding.json' if move and exact else 'rgmii-exact-toe-fixed.json' if exact else 'rgmii-adjacent-source-sliding.json' if move else 'rgmii-adjacent-source-native.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],rows=rows),indent=2)+'\n');print([(v['ref'],v['source_toes'],v['states'],len(v['candidates']),v['result'] and v['result']['length_mm']) for v in rows])
