"""Shortest planar grid path between two existing escape vias with no layer changes."""
import heapq,json,math,sys
from functools import lru_cache
from phy_bias_paths import space
def search(obj):
    a,z=map(tuple,obj['ends'])
    limit=math.dist(a,z)*1.65
    bounds=(min(a[0],z[0])-3500000,min(a[1],z[1])-3500000,max(a[0],z[0])+3500000,max(a[1],z[1])+3500000)
    clear=space(obj['geometry'],obj['width']/2+201000,bounds)
    if not clear(a,a) or not clear(z,z):return []
    step=50000
    queue=[(math.dist(a,z),0,a)];cost={a:0};parent={}
    while queue:
        _,c,u=heapq.heappop(queue)
        if c!=cost[u]:continue
        if math.dist(u,z)<=step*1.5 and clear(u,z):
            path=[z,u]
            while path[-1]!=a:path.append(parent[path[-1]])
            path=list(dict.fromkeys(reversed(path)));result=[a]
            while len(path)>1:
                i=max(i for i in range(1,len(path)) if clear(path[0],path[i]))
                result.append(path[i]);path=path[i:]
            return result
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)):
            v=u[0]+dx*step,u[1]+dy*step;nc=c+step*math.hypot(dx,dy)
            if nc+math.dist(v,z)>limit or not(bounds[0]<v[0]<bounds[2] and bounds[1]<v[1]<bounds[3]):continue
            if nc<cost.get(v,math.inf) and clear(u,v):
                cost[v]=nc;parent[v]=u;heapq.heappush(queue,(nc+math.dist(v,z),nc,v))
    return []
if __name__=='__main__':print(json.dumps(search(json.load(sys.stdin))))
