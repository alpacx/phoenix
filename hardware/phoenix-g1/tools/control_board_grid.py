"""Bidirectional endpoint selection across existing pad groups on four signal layers."""
import heapq,json,math,sys
from collections import defaultdict
from functools import lru_cache
from phy_bias_paths import space

def route(req):
    grid=req['grid_nm'];bounds=req['bounds'];step=grid
    clear=[space(layer,req.get('width_nm',200000)/2+202000,bounds) for layer in req['layers']]
    bore=[space(layer,req.get('via_nm',450000)/2+202000,bounds) for layer in req['through']]
    bore.append(space(req['via_keepouts'],req.get('via_nm',450000)/2+52000,bounds))
    @lru_cache(None)
    def via(x,y):return all(f((x,y),(x,y)) for f in bore)
    @lru_cache(None)
    def bridge(l,k,x,y):
        if not req.get('paired_vias'):return (x,y)
        for dx,dy in ((800000,0),(0,800000),(-800000,0),(0,-800000)):
            end=(x+dx,y+dy)
            if via(*end) and clear[l]((x,y),end) and clear[k]((x,y),end):return end
        return None
    @lru_cache(150000)
    def edge(l,x,y,u,v):return clear[l]((x,y),(u,v))
    goals=defaultdict(list);positions=[]
    for l,ends in enumerate(req['end']):
        for raw in ends:
            pos=tuple(raw)
            if not clear[l](pos,pos):continue
            positions.append(pos);goals[l,round(pos[0]/grid),round(pos[1]/grid)].append(pos)
    if not positions:return {}
    left,bottom=map(min,zip(*positions));right,top=map(max,zip(*positions))
    queue=[];cost={};parent={}
    def push(n,c,prev):
        if c>=cost.get(n,math.inf):return
        _,x,y=n
        h=math.hypot(max(0,left-x,x-right),max(0,bottom-y,y-top))
        cost[n]=c;parent[n]=prev;heapq.heappush(queue,(c+h,c,n))
    for l,points in enumerate(req['start']):
        for endpoint in points:
            a=tuple(endpoint)
            if not clear[l](a,a):continue
            for i in (-1,0,1):
                for j in (-1,0,1):
                    x=(round(a[0]/grid)+i)*grid;y=(round(a[1]/grid)+j)*grid
                    if clear[l](a,(x,y)):push((l,x,y),math.dist(a,(x,y)),('start',l,*a))
    while queue:
        _,c,n=heapq.heappop(queue)
        if c!=cost[n]:continue
        l,x,y=n
        for i in (-1,0,1):
            for j in (-1,0,1):
                for z in goals.get((l,round(x/grid)+i,round(y/grid)+j),()):
                    if math.dist((x,y),z)>1.5*grid or not clear[l]((x,y),z):continue
                    path=[(l,*z),n]
                    while parent[path[-1]][0]!='start':path.append(parent[path[-1]])
                    path.append(parent[path[-1]][1:]);path.reverse()
                    path=[v for k,v in enumerate(path) if k==0 or v!=path[k-1]]
                    result=[path[0]]
                    while len(path)>1:
                        k=1
                        if path[0][0]==path[1][0]:
                            for m in range(2,len(path)):
                                if path[m][0]!=path[0][0]:break
                                if clear[path[0][0]](path[0][1:],path[m][1:]):k=m
                        result.append(path[k]);path=path[k:]
                    bridges=[bridge(l,k,x,y) for (l,x,y),(k,u,v) in zip(result,result[1:]) if l!=k]
                    return {'path':result,'bridges':bridges}
        for i,j in ((0,1),(0,-1),(1,0),(-1,0),(1,1),(-1,-1),(-1,1),(1,-1)):
            u,v=x+i*step,y+j*step
            next_cost=c+math.hypot(i,j)*step
            if bounds[0]<u<bounds[2] and bounds[1]<v<bounds[3] and next_cost<cost.get((l,u,v),math.inf) and edge(l,x,y,u,v):push((l,u,v),next_cost,n)
        if any(c+2e6<cost.get((k,x,y),math.inf) for k in range(len(clear)) if k!=l) and via(x,y):
            for k in range(len(clear)):
                if k!=l and bridge(l,k,x,y):push((k,x,y),c+2e6,n)
    return {}
if __name__=='__main__':print(json.dumps(route(json.load(sys.stdin))))
