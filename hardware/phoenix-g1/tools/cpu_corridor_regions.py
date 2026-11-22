"""Intersect connected components of the copper-center free space across the two layers."""
import json
import sys
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union,nearest_points
d=json.load(sys.stdin)
region=box(29e6,4e6,77e6,36e6)
def blocked(layer,rad):
    copper,pads=layer
    items=[]
    for a,b,width in copper:
        line=Point(a) if a==b else LineString([a,b])
        if region.intersects(line.envelope.buffer(1e6)):
            items.append(line.buffer(width/2+rad,quad_segs=12))
    for points in pads:
        pad=box(*points)
        if region.intersects(pad.envelope.buffer(1e6)):items.append(pad.buffer(rad))
    return unary_union(items)
start=Point(d['start']);ends=[Point(xy) for xy in d['targets']]
by_layer=[]
all_components=[]
for lay in d['tracks']:
    free=region.difference(blocked(lay,602000))
    components=list(free.geoms) if hasattr(free,'geoms') else [free]
    all_components.append(components)
    src=unary_union([g for g in components if g.covers(start)])
    dst=unary_union([g for g in components if any(g.covers(q) for q in ends)])
    by_layer.append((src,dst))
rows=[]
for a,b in [(0,1),(1,0)]:
    src=by_layer[a][0];dst=by_layer[b][1]
    if src.is_empty or dst.is_empty:
        rows.append(dict(order=[a,b],source_empty=src.is_empty,target_empty=dst.is_empty));continue
    common=src.intersection(dst);edge=nearest_points(src,dst)
    row=dict(order=[a,b],closest_mm=src.distance(dst)/1e6,closest_points_nm=[list(pt.coords[0]) for pt in edge],common_area_mm2=common.area/1e12)
    if not common.is_empty and common.area:
        for layer in d['vias']:common=common.difference(blocked(layer,527000))
        for pts in d['lands']:
            g=box(*pts).buffer(425000)
            if common.intersects(g):common=common.difference(g)
        row['remaining_area_mm2']=common.area/1e12
        if common.area:row['candidate_nm']=list(common.representative_point().coords[0])
    rows.append(row)
from shapely.strtree import STRtree
from collections import deque
trees=[STRtree(gs) for gs in all_components]
roots=[(l,i) for l,gs in enumerate(all_components) for i,g in enumerate(gs) if g.covers(start)]
goals={(l,i) for l,gs in enumerate(all_components) for i,g in enumerate(gs) if any(g.covers(q) for q in ends)}
queue=deque(roots);parents={node:None for node in roots};found=None
while queue:
    node=queue.popleft()
    if node in goals:
        found=node;break
    layer,i=node
    here=all_components[layer][i]
    for j in trees[1-layer].query(here,predicate="intersects"):
        other=(1-layer,int(j))
        if other in parents or here.intersection(all_components[1-layer][j]).area<1:continue
        parents[other]=node;queue.append(other)
chain=[]
while found is not None:
    chain.append(found);found=parents[found]
chain.reverse()
print(json.dumps(dict(optimistic_multilayer_chain=chain,components_visited=len(parents),width_mm=.8,bounds_mm=[29,4,77,36],orders=rows,limits="Planar centerlines, axis-aligned pad envelopes; successful points still require native DRC, keepout and return inspection.")))
