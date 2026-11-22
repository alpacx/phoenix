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
    margin=data.get("reference_half_width_nm",105000)
    valid=unary_union([plane,Point(a).buffer(590000),Point(z).buffer(590000)]).buffer(-margin)
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
    broadside=[]
    for start,stop,width in data.get("projected_foreign",[]):
        if start==stop:continue
        segment=LineString((start,stop))
        if roi.intersects(segment):
            angle=math.atan2(stop[1]-start[1],stop[0]-start[0])
            broadside.append((segment.buffer(width/2+202000),angle))
    directional=STRtree([shape for shape,angle in broadside]) if broadside else None
    def legal(u,v):
        line=LineString((u,v)) if u!=v else Point(u)
        if not valid.covers(line) or len(tree.query(line,predicate='intersects')):return False
        if directional is not None and u!=v:
            angle=math.atan2(v[1]-u[1],v[0]-u[0])
            for index in directional.query(line,predicate="intersects"):
                delta=abs((angle-broadside[index][1]+math.pi/2)%math.pi-math.pi/2)
                if delta<math.pi/12:return False
        return True
    def compact_path(path):
        out=[]
        for point in path:
            if out and point==out[-1]:continue
            if len(out)>=2:
                p,q=out[-2:]
                if (q[0]-p[0])*(point[1]-q[1])==(q[1]-p[1])*(point[0]-q[0]) and legal(p,point):out.pop()
            out.append(point)
        if data.get("compact_45"):
            # Choose the smallest number of legal 45-degree/axial segments, then length.
            best={0:(0,0,[])}
            for j in range(1,len(out)):
                for i in range(j):
                    u,v=out[i],out[j];dx=v[0]-u[0];dy=v[1]-u[1]
                    diagonal=min(abs(dx),abs(dy))
                    d=(int(math.copysign(diagonal,dx)),int(math.copysign(diagonal,dy)))
                    for elbow in ((u[0]+d[0],u[1]+d[1]),(v[0]-d[0],v[1]-d[1])):
                        tail=[pt for k,pt in enumerate((elbow,v)) if pt!=(u,elbow)[k]]
                        if not all(legal(k,l) for k,l in zip([u]+tail,tail)):continue
                        count,length,history=best[i]
                        value=(count+len(tail),length+sum(math.dist(k,l) for k,l in zip([u]+tail,tail)),history+tail)
                        if j not in best or value < best[j]:best[j]=value
                if j not in best:
                    prev_cost,prev_length,prev_path=best[j-1]
                    assert legal(out[j-1],out[j])
                    best[j]=(prev_cost+1,prev_length+math.dist(out[j-1],out[j]),prev_path+[out[j]])
            out=[out[0]]+best[len(out)-1][2]
        return {'path':out}
    if "preset_path" in data:
        path=[tuple(point) for point in data["preset_path"]]
        if not all(legal(a,b) for a,b in zip(path,path[1:])):return {"path_invalid":True}
        return compact_path(path)
    dirs=[(dx,dy) for dx in (-grid,0,grid) for dy in (-grid,0,grid) if dx or dy]
    def ends(pt):
        base=tuple(round(v/grid)*grid for v in pt)
        return {u for dx in (-grid,0,grid) for dy in (-grid,0,grid) if legal(pt,u:=(base[0]+dx,base[1]+dy))}
    starts,endsites=ends(a),ends(z)
    frontier=data.get("collect_frontier",False)
    if not starts or (not frontier and not endsites):return dict(starts=len(starts),ends=len(endsites),start_copper=bool(legal(a,a)),end_copper=bool(legal(z,z)))
    dist={s:math.dist(a,s) for s in starts};prev={s:a for s in starts}
    queue=[(c+math.dist(s,z),c,s) for s,c in dist.items()];heapq.heapify(queue)
    while queue:
        _,c,u=heapq.heappop(queue)
        if c!=dist[u]:continue
        if not frontier and u in endsites:
            path=[z,u]
            while u!=a:u=prev[u];path.append(u)
            path.reverse()
            return compact_path(path)
        for dx,dy in dirs:
            v=(u[0]+dx,u[1]+dy);score=c+math.hypot(dx,dy)
            if score+math.dist(v,z)>data.get("max_path_nm",1.45*math.dist(a,z)) or score>=dist.get(v,math.inf):continue
            if legal(u,v):
                dist[v]=score;prev[v]=u;heapq.heappush(queue,(score+math.dist(v,z),score,v))
    result=dict(starts=len(starts),ends=len(endsites),visited=len(dist))
    if frontier:result['frontier']=[[list(pt),list(prev.get(pt,a)),dist[pt]] for pt in dist]
    return result
if __name__=='__main__':print(json.dumps(route(json.load(sys.stdin))))
