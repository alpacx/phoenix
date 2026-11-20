"""Find a 45-degree single-layer path whose full strip has a reference plane."""
import heapq,json,math,sys
import shapely
from shapely.geometry import Polygon,LineString,Point,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
def route(data):
    grid=100000
    a,z=map(tuple,data['via_nm'])
    bounds=(min(a[0],z[0])-3000000,min(a[1],z[1])-3000000,max(a[0],z[0])+3000000,max(a[1],z[1])+3000000)
    roi=box(*bounds)
    plane=unary_union([Polygon(shell,holes).buffer(0) for shell,holes in data['plane']]).intersection(roi)
    valid=unary_union([plane,Point(a).buffer(590000),Point(z).buffer(590000)]).buffer(-105000)
    shapely.prepare(valid)
    seg,pads,outlines=data['geometry']
    obstacles=[]
    for u,v,w in seg:
        line=Point(u) if u==v else LineString((u,v))
        if roi.intersects(line):obstacles.append(line.buffer(w/2+305000))
    for bb in pads:
        shape=box(*bb)
        if roi.intersects(shape):obstacles.append(shape.buffer(305000))
    obstacles.extend(Polygon(poly).buffer(105000) for poly in outlines)
    tree=STRtree(obstacles)
    def legal(u,v):
        line=LineString((u,v)) if u!=v else Point(u)
        return valid.covers(line) and not len(tree.query(line,predicate='intersects'))
    dirs=[(dx,dy) for dx in (-grid,0,grid) for dy in (-grid,0,grid) if dx or dy]
    def ends(pt):
        base=tuple(round(v/grid)*grid for v in pt)
        return {u for dx in (-grid,0,grid) for dy in (-grid,0,grid) if legal(pt,u:=(base[0]+dx,base[1]+dy))}
    starts,endsites=ends(a),ends(z)
    if not starts or not endsites:return dict(starts=len(starts),ends=len(endsites),start_copper=bool(legal(a,a)),end_copper=bool(legal(z,z)))
    dist={s:math.dist(a,s) for s in starts};prev={s:a for s in starts}
    queue=[(c+math.dist(s,z),c,s) for s,c in dist.items()];heapq.heapify(queue)
    while queue:
        _,c,u=heapq.heappop(queue)
        if c!=dist[u]:continue
        if u in endsites:
            path=[z,u]
            while u!=a:u=prev[u];path.append(u)
            path.reverse()
            out=[]
            for point in path:
                if out and point==out[-1]:continue
                if len(out)>=2:
                    p,q=out[-2:]
                    if (q[0]-p[0])*(point[1]-q[1])==(q[1]-p[1])*(point[0]-q[0]) and legal(p,point):out.pop()
                out.append(point)
            return {'path':out}
        for dx,dy in dirs:
            v=(u[0]+dx,u[1]+dy);score=c+math.hypot(dx,dy)
            if score+math.dist(v,z)>1.45*math.dist(a,z) or score>=dist.get(v,math.inf):continue
            if legal(u,v):
                dist[v]=score;prev[v]=u;heapq.heappush(queue,(score+math.dist(v,z),score,v))
    return dict(starts=len(starts),ends=len(endsites),visited=len(dist))
if __name__=='__main__':print(json.dumps(route(json.load(sys.stdin))))
