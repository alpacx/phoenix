"""Reconnect a displaced front-side trace to its two original electrical anchors."""
from collections import Counter,defaultdict
import heapq,math
import pcbnew as p
from pcb_bounds import inflated_box
v=lambda xy:p.VECTOR2I(*xy)
side=p.F_Cu
def wire(b,a,z,net,width):
 t=p.PCB_TRACK(b);t.SetStart(v(a));t.SetEnd(v(z));t.SetLayer(side);t.SetNetCode(net);t.SetWidth(width);return t
def compact(path):
 pts=[path[0]]
 for mid,n in zip(path[1:],path[2:]+[None]):
  if n:
   d=(mid[0]-pts[-1][0],mid[1]-pts[-1][1]);e=(n[0]-mid[0],n[1]-mid[1])
   if d[0]*e[1]==d[1]*e[0] and d[0]*e[0]+d[1]*e[1]>0:continue
  pts.append(mid)
 return pts
def recover(b,old,net,workaround, search_all_obstacles=False, exact_destination=False, exact_start=False, minimum_clearance_nm=None):
    ends=Counter(pt for t in old for pt in t[:2]);outer=[pt for pt,n in ends.items() if n==1]
    if len(outer)!=2:return None,dict(reason='disjoint original anchors')
    a,z=outer;w,code=old[0][2:];assert all(t[2]==w for t in old)
    obj=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if o.GetNetCode()!=code and inflated_box(o,round(math.dist(a,z)+2700000) if search_all_obstacles else 4600000).Contains(v(a))]
    pads=[q for f in b.GetFootprints() for q in f.Pads() if q.GetNetCode()==code and q.IsOnLayer(side)]
    t=wire(b,a,z,code,w);buckets=defaultdict(list);step=25000;cell=500000
    for o in obj:
        sh=o.GetEffectiveShape(side) if o.IsOnLayer(side) else None
        h=o.GetEffectiveHoleShape() if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x else None
        if sh is None and h is None:continue
        c=78200 if isinstance(o,p.PAD) and o.GetParentFootprint().GetReference()=='U1' or o.GetNetname().startswith('LPDDR4_') else 202000
        if minimum_clearance_nm is not None:c=max(c,minimum_clearance_nm)
        bb=inflated_box(o,500000)
        for i in range(bb.GetLeft()//cell,bb.GetRight()//cell+1):
            for j in range(bb.GetTop()//cell,bb.GetBottom()//cell+1):buckets[i,j].append((sh,h,c))
    def free(x,y):
        t.SetStart(v(x));t.SetEnd(v(y));sh=t.GetEffectiveShape(side)
        return not any(o is not None and sh.Collide(o,c) or h is not None and sh.Collide(h,252000) for o,h,c in buckets[x[0]//cell,x[1]//cell])
    def options(pt):
        pad=next((q for q in pads if q.HitTest(v(pt))),None)
        if not pad:return [pt] if free(pt,pt) else []
        pos=tuple(pad.GetPosition());return [(pos[0]+i*step,pos[1]+j*step) for i in range(-5,6) for j in range(-5,6) if math.hypot(i,j)*step<=100000 and free((pos[0]+i*step,pos[1]+j*step),(pos[0]+i*step,pos[1]+j*step))]
    starts=([a] if free(a,a) else []) if exact_start else options(a);goals=([z] if free(z,z) else []) if exact_destination else options(z)
    if not starts or not goals:return None,dict(reason='anchor blocked',starts=len(starts),goals=len(goals))
    goalset=set(goals);dist=dict.fromkeys(starts,0);prev={};queue=[(math.dist(s,z),0,s) for s in starts];heapq.heapify(queue);limit=math.dist(a,z)+2200000
    while queue:
        _,cost,pt=heapq.heappop(queue)
        if cost!=dist[pt]:continue
        target=next((g for g in goals if math.dist(pt,g)<=35000 and free(pt,g)),None)
        if target is not None:
            path=[pt]
            while path[-1] in prev:path.append(prev[path[-1]])
            path.reverse()
            if path[-1]!=target:path.append(target)
            return compact(path),dict(width=w,code=code,length_mm=(cost+math.dist(pt,target))/1e6)
        for i,j in ((-1,0),(1,0),(0,-1),(0,1),(1,1),(1,-1),(-1,1),(-1,-1)):
            dest=(pt[0]+i*step,pt[1]+j*step);c=cost+math.hypot(i,j)*step
            if c>=dist.get(dest,math.inf) or c+math.dist(dest,z)>limit or not free(pt,dest):continue
            dist[dest]=c;prev[dest]=pt;heapq.heappush(queue,(c+math.dist(dest,z),c,dest))
    return None,dict(reason='closed front channel',reachable=len(dist),starts=len(starts),goals=len(goals))
