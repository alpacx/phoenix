"""Find a shared reachable island for a pair of through vias on two power layers."""
import collections, json, math, sys
from phy_corridor_grid import clearance

data=json.load(sys.stdin)
layers=[clearance(*d,726000) for d in data['power']]
vias=[clearance(*d,501000) for d in data['all']]
step=150000
directions=[(u*step,v*step) for u in (-1,0,1) for v in (-1,0,1) if u or v]
def flood(origin,valid):
    anchor=tuple(round(i/step)*step for i in origin)
    if not valid(origin,anchor):return {}
    parent={anchor:tuple(origin)}
    queue=collections.deque([anchor])
    while queue:
        u=queue.popleft()
        for dx,dy in directions:
            w=(u[0]+dx,u[1]+dy)
            if w in parent or not(48e6<w[0]<68e6 and 17e6<w[1]<34e6):continue
            if valid(u,w):
                parent[w]=u
                queue.append(w)
    return parent
starts=[(55110000,27050000),(61740000,24575000)]
trees=[flood(s,fn) for s,fn in zip(starts,layers)]
common=sorted(trees[0].keys()&trees[1].keys(),key=lambda u:sum(math.dist(u,s) for s in starts))
def path(tree,origin,u,valid):
    arr=[u]
    while arr[-1]!=origin:arr.append(tree[arr[-1]])
    arr.reverse()
    result=[arr[0]]
    while len(arr)>1:
        j=max(j for j in range(1,len(arr)) if valid(arr[0],arr[j]))
        result.append(arr[j]);arr=arr[j:]
    return result
valid_sites=[]
for u in common:
    for dx in (-50000,0,50000):
        for dy in (-50000,0,50000):
            v=(u[0]+dx,u[1]+dy)
            if all(fn(v,v) for fn in vias) and all(fn(u,v) for fn in layers):
                valid_sites.append((v,u))
for u,anchor in valid_sites:
    for v,_ in valid_sites:
        if 620000<=math.dist(u,v)<=1800000 and all(fn(u,v) for fn in layers):
            print(json.dumps(dict(vias=[u,v],paths=[path(t,s,anchor,fn)+([u] if anchor!=u else []) for t,s,fn in zip(trees,starts,layers)])));sys.exit()
print(json.dumps(dict(vias=[],reachable=list(map(len,trees)),common=len(common),valid_sites=valid_sites)))
