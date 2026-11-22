"""Find connected components of free area for the middle of a pair with common routing clearance."""
import heapq
import json
import math
import sys
import numpy as np
import shapely
from scipy.ndimage import label
from scipy.spatial import cKDTree
from shapely.geometry import Polygon,LineString,Point,box
from shapely.ops import unary_union

def run(d):
    a,b=d["centers"];step=100000
    xl,yl=[math.floor((min(i,j)-3000000)/step)*step for i,j in zip(a,b)]
    xh,yh=[math.ceil((max(i,j)+3000000)/step)*step for i,j in zip(a,b)]
    roi=box(xl,yl,xh,yh);obstacles=[]
    for u,v,w in d["geometry"][0]:
        geo=Point(u) if u==v else LineString([u,v])
        if geo.intersects(roi):obstacles.append(geo.buffer(w/2+527000))
    for bounds in d["geometry"][1]:
        obj=box(*bounds)
        if obj.intersects(roi):obstacles.append(obj.buffer(527000))
    for outline in d["geometry"][2]:
        obj=Polygon(outline)
        if obj.intersects(roi):obstacles.append(obj.buffer(325000))
    plane=unary_union([Polygon(outer,holes).buffer(0) for outer,holes in d["plane"]]).intersection(roi)
    # Half the mesh diagonal prevents raster paths jumping between disjoint polygons.
    guard=step/math.sqrt(2)
    metal=roi.difference(unary_union(obstacles))
    safe=plane.buffer(-425000).intersection(metal).buffer(-guard)
    x,y=np.meshgrid(np.arange(xl,xh+step,step),np.arange(yl,yh+step,step))
    ok=shapely.contains_xy(safe,x,y);components,count=label(ok)
    radii=d.get("gate_radii_nm",[1500000,1500000])
    at=[]
    for (px,py),rad in zip((a,b),radii):
        values=components[(x-px)**2+(y-py)**2<=rad**2]
        at.append(set(int(i) for i in values if i))
    common=at[0]&at[1]
    fronts=[list(zip(x[np.isin(components,list(ids))].tolist(),y[np.isin(components,list(ids))].tolist())) for ids in at]
    middle=None
    if common and d.get("route"):
        kept=set().union(common)
        allowed=np.isin(components,list(kept))
        deleted=np.array(d.get("released_nm",[]))
        # Encourage a corridor that permits reinstating the unfinished signal fanouts.
        risk=np.zeros(x.shape,dtype=int)
        for px,py in deleted:
            risk+=((x-px)**2+(y-py)**2<855000**2)
        ends=(x-b[0])**2+(y-b[1])**2<=radii[1]**2
        starts=np.argwhere(allowed & ((x-a[0])**2+(y-a[1])**2<=radii[0]**2))
        costs={};parents={};queue=[]
        for iy,ix in starts:
            k=int(iy),int(ix);costs[k]=math.hypot(x[k]-a[0],y[k]-a[1]);heapq.heappush(queue,(costs[k],k))
        best=math.inf;last=None
        forsearch=[(dy,dx) for dx in (-1,0,1) for dy in (-1,0,1) if dx or dy]
        while queue:
            cost,node=heapq.heappop(queue)
            if cost!=costs[node] or cost>=best:continue
            iy,ix=node
            if ends[node]:
                total=cost+math.hypot(x[node]-b[0],y[node]-b[1])
                if total<best:best,last=total,node
            for dy,dx in forsearch:
                dest=(iy+dy,ix+dx)
                if not (0<=dest[0]<x.shape[0] and 0<=dest[1]<x.shape[1] and allowed[dest]):continue
                if dy and dx and not (allowed[iy+dy,ix] and allowed[iy,ix+dx]):continue
                advance=step*math.hypot(dx,dy)*(1+0.65*risk[dest])
                if cost+advance<costs.get(dest,math.inf):
                    costs[dest]=cost+advance;parents[dest]=node;heapq.heappush(queue,(cost+advance,dest))
        if last:
            track=[last]
            while track[-1] in parents:track.append(parents[track[-1]])
            track.reverse()
            pts=[]
            for iy,ix in track:
                point=(int(x[iy,ix]),int(y[iy,ix]))
                if len(pts)>1:
                    m,n=pts[-2:]
                    if (n[0]-m[0])*(point[1]-n[1])==(n[1]-m[1])*(point[0]-n[0]):pts.pop()
                pts.append(point)
            line=LineString(pts);middle={"points_nm":pts,"length_mm":line.length/1e6,
                "released_barrels_within_855um":sum(line.distance(Point(pt))<855000 for pt in deleted)}
    separate={}
    for group,geometry in (("plane_only",plane.buffer(-425000-guard)),("copper_only",metal.buffer(-guard))):
        ids,_=label(shapely.contains_xy(geometry,x,y));ends=[set(int(k) for k in ids[(x-px)**2+(y-py)**2<=1500000**2] if k) for px,py in (a,b)]
        separate[group]=bool(ends[0]&ends[1])
    gap=None
    if fronts[0] and fronts[1]:
        lengths,which=cKDTree(fronts[1]).query(fronts[0]);i=int(np.argmin(lengths))
        gap={"mm":round(lengths[i]/1e6,3),"positions_nm":[fronts[0][i],fronts[1][which[i]]]}
    return {"reachable":fronts,"middle":middle,"separate":separate,"nearest_gap":gap,"gates_connected":bool(common),"gate_components":[len(k) for k in at],"common_cells":len(np.flatnonzero(np.isin(components,list(common))))}
if __name__=="__main__":print(json.dumps(run(json.load(sys.stdin))))
