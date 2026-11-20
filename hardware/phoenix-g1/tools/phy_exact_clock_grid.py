"""Route short clock sections with the actual saved KiCad pad shapes."""
import heapq,math
from functools import lru_cache
import pcbnew as p
def solve(board,net,layer,start,end,width,site):
    reserve=p.PCB_VIA(board);reserve.SetPosition(p.VECTOR2I(*site));reserve.SetWidth(450000);reserve.SetDrill(200000);reserve.SetLayerPair(p.F_Cu,p.B_Cu)
    copper=[k for k in list(board.GetTracks())+[q for f in board.GetFootprints() for q in f.Pads()] if k.IsOnLayer(layer) and k.GetNetname()!=net]
    copper.append(reserve)
    shapes={}
    for k in copper:
        box=k.GetBoundingBox().Inflate(500000)
        if box.GetRight()<55000000 or box.GetLeft()>64000000 or box.GetBottom()<28000000 or box.GetTop()>37000000:continue
        shape=k.GetEffectiveShape(layer)
        for i in range(box.GetLeft()//500000,box.GetRight()//500000+1):
            for j in range(box.GetTop()//500000,box.GetBottom()//500000+1):
                shapes.setdefault((i,j),[]).append(shape)
    areas=[z.Outline() for z in board.Zones() if z.GetIsRuleArea() and z.IsOnLayer(layer) and z.GetDoNotAllowTracks()]
    edge=p.PCB_TRACK(board);edge.SetWidth(width);edge.SetLayer(layer)
    def clear(a,z):
        edge.SetStart(p.VECTOR2I(*a));edge.SetEnd(p.VECTOR2I(*z));s=edge.GetEffectiveShape(layer)
        return all(not s.Collide(o,200000) for o in shapes.get((a[0]//500000,a[1]//500000),[])) and all(not area.Collide(s,0) for area in areas)
    if not clear(start,start) or not clear(end,end):return []
    step=25000;queue=[(math.dist(start,end),0,start)];best={start:0};parent={}
    while queue:
        _,c,a=heapq.heappop(queue)
        if c!=best[a]:continue
        if math.dist(a,end)<=step*1.5 and clear(a,end):
            pts=[end] if a!=end else []
            while a!=start:pts.append(a);a=parent[a]
            pts.append(start);pts.reverse()
            path=[pts[0]]
            for i in range(1,len(pts)-1):
                x,y=pts[i-1];u,v=pts[i];r,s=pts[i+1]
                if (u-x)*(s-v)!=(v-y)*(r-u):path.append(pts[i])
            path.append(pts[-1]);return path
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)):
            z=(a[0]+dx*step,a[1]+dy*step)
            if not (56000000<=z[0]<=63000000 and 28500000<=z[1]<=36500000):continue
            d=c+step*math.hypot(dx,dy)
            if d<best.get(z,math.inf) and clear(a,z):
                best[z]=d;parent[z]=a;heapq.heappush(queue,(d+math.dist(z,end),d,z))
    return []
