"""Find a path from any of a set of power lands to reachable existing copper on one layer."""
import heapq
import json
import math
import sys
from phy_bias_paths import space
d=json.load(sys.stdin)
starts=list(map(tuple,d["sites"]));targets=list(map(tuple,d["target"]));points=starts+targets
bounds=[min(x for x,y in points)-2000000,min(y for x,y in points)-2000000,max(x for x,y in points)+2000000,max(y for x,y in points)+2000000]
clear=space(d["geometry"],d["width"]/2+202000,bounds)
dirs=[(dx*50000,dy*50000) for dx in (-1,0,1) for dy in (-1,0,1) if dx or dy]
cost={};queue=[];parents={}
for at in starts:
    if clear(at,at):cost[at]=0;heapq.heappush(queue,(0,at))
stop=None
while queue:
    dist,at=heapq.heappop(queue)
    if dist!=cost[at]:continue
    hit=next((t for t in targets if math.dist(at,t)<=100000 and clear(at,t)),None)
    if hit:stop=at,hit;break
    for dx,dy in dirs:
        z=at[0]+dx,at[1]+dy
        nd=dist+math.hypot(dx,dy)
        if nd+min(math.dist(z,t) for t in targets)>d["limit"] or nd>=cost.get(z,math.inf):continue
        if clear(at,z):cost[z]=nd;parents[z]=at;heapq.heappush(queue,(nd,z))
path=[]
if stop:
    tip,target=stop;path=[tip]
    while path[-1] in parents:path.append(parents[path[-1]])
    path.reverse()
    if path[-1]!=target:path.append(target)
    compact=[]
    for pt in path:
        if len(compact)>1:
            a,z=compact[-2:]
            if (z[0]-a[0])*(pt[1]-z[1])==(z[1]-a[1])*(pt[0]-z[0]):compact.pop()
        compact.append(pt)
    path=compact
nearest=min(((math.dist(pt,t),pt,t) for pt in cost for t in targets),default=None)
print(json.dumps({"front_nodes":len(cost),"path":path,"closest":nearest,"front":list(cost) if d.get("frontier") else []}))
