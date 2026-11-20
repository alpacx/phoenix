"""Search local 0.20 mm pull-up traces with a penalized through-via transition."""
import heapq,json,math,sys
from functools import lru_cache
from shapely.geometry import LineString,Point,Polygon,box
from shapely.strtree import STRtree

def space(items,margin,limits):
    copper,pads,*outlines=items
    shapes=[]
    roi=box(*limits).buffer(2e6)
    for a,z,width in copper:
        line=Point(a) if a==z else LineString([a,z])
        if roi.intersects(line):shapes.append(line.buffer(width/2+margin,quad_segs=24))
    for bounds in pads:
        pad=box(*bounds)
        if roi.intersects(pad):shapes.append(pad.buffer(margin))
    for polygons in outlines:
        for points in polygons:
            poly=Polygon(points)
            if roi.intersects(poly):shapes.append(poly.buffer(margin))
    tree=STRtree(shapes)
    def clear(a,z):
        shape=Point(a) if a==z else LineString([a,z])
        return len(tree.query(shape,predicate='intersects'))==0
    return clear

def search(data):
    limits=data.get("bounds",[49e6,16e6,78e6,39e6])
    step=data.get("grid_nm",200000)
    clear=[space(g,data.get('trace_width_nm',200000)/2+202000,limits) for g in data['layers']]
    drill=[space(g,data.get('via_nm',450000)/2+202000,limits) for g in data['through']]
    if 'via_keepouts' in data:
        drill.append(space(data['via_keepouts'],data.get('via_nm',450000)/2+52000,limits))
    @lru_cache(None)
    def via(x,y):return all(f((x,y),(x,y)) for f in drill)
    queue=[];cost={};parent={}
    @lru_cache(None)
    def edge(l,x,y,u,v):return clear[l]((x,y),(u,v))
    def push(l,x,y,c,prev):
        n=(l,x,y)
        if c>=cost.get(n,math.inf):return
        parent[n]=prev;cost[n]=c
        heapq.heappush(queue,(c+min(math.dist((x,y),g) for g in goals),c,n))
    goals=[tuple(v) for v in data['goals'].values()]
    for l,points in enumerate(data['seeds']):
        for p in points:
            x,y=[round(i/step)*step for i in p]
            for dx in (-step,0,step):
                for dy in (-step,0,step):
                    u,v=x+dx,y+dy
                    if clear[l](p,(u,v)):push(l,u,v,math.dist(p,(u,v)),('seed',l,*p))
    while queue:
        _,c,n=heapq.heappop(queue)
        if cost[n]!=c:continue
        l,x,y=n
        for ref,g in data['goals'].items():
            if l==data.get('goal_layer',0) and math.dist((x,y),g)<1.5*step and clear[0]((x,y),g):
                path=[(l,*g),n]
                while parent[path[-1]][0]!='seed':path.append(parent[path[-1]])
                path.append(parent[path[-1]][1:]);path.reverse()
                path=list(dict.fromkeys(path))
                result=[path[0]]
                while len(path)>1:
                    idx=1
                    if path[0][0]==path[1][0]:
                        for i in range(2,len(path)):
                            if path[i][0]!=path[0][0]:break
                            if clear[path[0][0]](path[0][1:],path[i][1:]):idx=i
                    result.append(path[idx]);path=path[idx:]
                return dict(ref=ref,path=result)
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)):
            u,v=x+dx*step,y+dy*step
            nc=c+math.hypot(dx,dy)*step
            if limits[0]<u<limits[2] and limits[1]<v<limits[3] and nc<cost.get((l,u,v),math.inf) and edge(l,x,y,u,v):push(l,u,v,nc,n)
        for other in range(len(clear)):
            if other!=l and c+2e6<cost.get((other,x,y),math.inf) and via(x,y):
                push(other,x,y,c+2e6,n)
    return {}
if __name__=='__main__':print(json.dumps(search(json.load(sys.stdin))))
