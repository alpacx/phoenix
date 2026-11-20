"""Search inner-layer copper clearance using capsule obstacles and conservative pad bounds."""
import json, math, heapq, sys
from shapely.geometry import LineString, Point, box
from shapely.strtree import STRtree

def clearance(obstacles,pads,margin):
    area=box(46e6,14e6,70e6,37e6)
    polygons=[]
    for u,v,w in obstacles:
        line=Point(u) if u==v else LineString([u,v])
        if area.intersects(line):
            polygons.append(line.buffer(w/2+margin,quad_segs=24))
    polygons.extend(box(*r).buffer(margin) for r in pads if area.intersects(box(*r)))
    tree=STRtree(polygons)
    def free(a,z):
        line=Point(a) if a==z else LineString([a,z])
        return len(tree.query(line,predicate="intersects"))==0
    return free

def solve(data):
    a,z,obstacles,pads,*margins=data
    a,z=tuple(a),tuple(z)
    free=clearance(obstacles,pads,margins[0] if margins else 726000)
    if not free(a,a) or not free(z,z):return []
    steps=[(dx*25000,dy*25000) for dx in (-1,0,1) for dy in (-1,0,1) if dx or dy]
    queue=[(math.dist(a,z),0,a)]
    best={a:0}
    parent={}
    while queue:
        _,cost,u=heapq.heappop(queue)
        if best[u]!=cost:continue
        if math.dist(u,z)<25000*2 and free(u,z):
            path=[z,u]
            while path[-1]!=a:path.append(parent[path[-1]])
            path.reverse()
            reduced=[a]
            while reduced[-1]!=z:
                j=max(i for i,w in enumerate(path) if free(reduced[-1],w))
                reduced.append(path[j])
                path=path[j:]
            return [tuple(v/1e6 for v in w) for w in reduced]
        for dx,dy in steps:
            w=(u[0]+dx,u[1]+dy)
            if not (48e6<w[0]<68e6 and 16e6<w[1]<35e6):continue
            c=cost+math.hypot(dx,dy)
            if c<best.get(w,math.inf) and free(u,w):
                best[w]=c
                parent[w]=u
                heapq.heappush(queue,(c+math.dist(w,z),c,w))
    print("visited",len(best),file=sys.stderr)
    return []

if __name__=="__main__":print(json.dumps(solve(json.load(sys.stdin))))
