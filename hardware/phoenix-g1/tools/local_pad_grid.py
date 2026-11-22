"""Bounded single-face search from a pad to nearby legal component placements."""
import heapq,json,math,sys
from functools import lru_cache
from phy_bias_paths import space
data=json.load(sys.stdin);x,y=data['origin']
free=space(data['geometry'],302000,(x-7e6,y-7e6,x+7e6,y+7e6))
step=100000
def snap(p):return tuple(round(v/step)*step for v in p)
@lru_cache(None)
def clear(a,z):return free(a,z)
queue=[];cost={};parent={}
for s in data['seeds']:
    a=tuple(s);n=snap(a)
    if clear(a,n):heapq.heappush(queue,(math.dist(a,n),n));cost[n]=math.dist(a,n);parent[n]=('start',a)
while queue:
    c,u=heapq.heappop(queue)
    if c!=cost[u]:continue
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)):
        w=u[0]+dx*step,u[1]+dy*step;nc=c+step*math.hypot(dx,dy)
        if nc<5e6 and nc<cost.get(w,math.inf) and clear(u,w):
            parent[w]=u;cost[w]=nc;heapq.heappush(queue,(nc,w))
result=[]
for key,point in data['goals'].items():
    z=tuple(point);n=snap(z)
    if n not in cost or not clear(n,z):continue
    path=[z,n]
    while parent[path[-1]][0]!='start':path.append(parent[path[-1]])
    path.append(parent[path[-1]][1]);path=list(dict.fromkeys(reversed(path)));out=[path[0]]
    while len(path)>1:
        j=max(i for i in range(1,len(path)) if clear(path[0],path[i]))
        out.append(path[j]);path=path[j:]
    result.append(dict(index=key,path=out,length=sum(math.dist(a,z) for a,z in zip(out,out[1:]))))
print(json.dumps(sorted(result,key=lambda r:r['length'])))
