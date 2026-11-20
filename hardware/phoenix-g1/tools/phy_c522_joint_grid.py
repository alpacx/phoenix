"""Search a power path with the actual candidate ground pad as an obstacle."""
import json,sys,math
from collections import deque
from phy_corridor_grid import clearance
from shapely.geometry import box,LineString,Point

data=json.load(sys.stdin)
primary=clearance(*data['geometry'],976000)
grid=50000
steps=[(i*grid,j*grid) for i in (-1,0,1) for j in (-1,0,1) if i or j]
def anchor(pos):return tuple(round(v/grid)*grid for v in pos)
def base_edge(a,z):
    if z<a:a,z=z,a
    key=a,z
    if key not in cache:cache[key]=primary(a,z)
    return cache[key]
cache={}
srcs={anchor(src):tuple(src) for src in data['starts'] if primary(src,anchor(src))}
results=[]
for site in data['sites']:
    tip=tuple(round(i*1e6) for i in site['wide_tip'])
    origin=anchor(tip)
    extra=box(*site['ground_box']).buffer(976000)
    def free(a,z):
        return base_edge(a,z) and not extra.intersects(Point(a) if a==z else LineString([a,z]))
    if not free(tip,origin):continue
    queue=deque([origin]);parent={origin:tip}
    while queue:
        u=queue.popleft()
        if u in srcs and free(u,srcs[u]):
            path=[srcs[u],u]
            while path[-1]!=tip:path.append(parent[path[-1]])
            path=list(dict.fromkeys(path))
            reduced=[path[0]]
            while len(path)>1:
                j=max(i for i in range(1,len(path)) if free(path[0],path[i]))
                reduced.append(path[j]);path=path[j:]
            results.append(dict(site=site,power=[[v/1e6 for v in w] for w in reduced]))
            break
        for dx,dy in steps:
            w=u[0]+dx,u[1]+dy
            if w not in parent and 53e6<w[0]<69e6 and 25e6<w[1]<38e6 and free(u,w):
                parent[w]=u;queue.append(w)
print(json.dumps(results))
