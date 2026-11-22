"""Measure local, finite-width return paths from each new ground pad to independently grounded barrels."""
from collections import defaultdict
import heapq
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

if '--extract' in sys.argv:
    import pcbnew as p
    infile,outfile=sys.argv[-2:];b=p.LoadBoard(infile);b.BuildConnectivity()
    def uid(o):return o.m_Uuid.AsString()
    def ring(chain):return [tuple(chain.CPoint(i)) for i in range(chain.PointCount())]
    def polygons(poly):
        return [dict(exterior=ring(poly.COutline(i)),holes=[ring(poly.CHole(i,j)) for j in range(poly.HoleCount(i))]) for i in range(poly.OutlineCount())]
    group={uid(o) for o in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('U4').FindPadByNumber('69'))}
    reference=[z.GetFilledPolysList(p.In4_Cu) for z in b.Zones() if z.IsOnLayer(p.In4_Cu) and z.GetNetname()=='GND' and not z.GetIsRuleArea()]
    grounded=[];copper=[]
    items=list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]
    for item in items:
        if uid(item) not in group or not item.IsOnLayer(p.B_Cu):continue
        box=item.GetBoundingBox()
        if box.GetRight()<50000000 or box.GetLeft()>69500000 or box.GetTop()>18000000:continue
        shape=p.SHAPE_POLY_SET()
        item.TransformShapeToPolygon(shape,p.B_Cu,0,3000,p.ERROR_INSIDE)
        copper.extend(polygons(shape))
        if isinstance(item,p.PCB_VIA) and item.GetViaType()==p.VIATYPE_THROUGH and item.GetDrillValue()>=200000 and any(z.Contains(item.GetPosition()) for z in reference):grounded.append(uid(item))
    Path(outfile).write_text(json.dumps(dict(copper=copper,grounded=grounded)));os._exit(0)

from shapely.geometry import Polygon,Point,LineString
from shapely.ops import unary_union
from shapely.prepared import prep
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
report=json.loads((root/'rotated-buck-return-zone.json').read_text())
with tempfile.TemporaryDirectory() as d:
    extract=Path(d)/'copper.json'
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3',__file__,'--extract',str(root/report['board']),str(extract)],check=True,capture_output=True)
    geometry=json.loads(extract.read_text())
def mm(xy):return tuple(v/1e6 for v in xy)
def polygons(rows):
    for row in rows:
        shape=Polygon([mm(xy) for xy in row['exterior']],[[mm(xy) for xy in hole] for hole in row['holes']])
        if not shape.is_empty:yield shape if shape.is_valid else shape.buffer(0)
surface=unary_union(list(polygons(report['polygons']+geometry['copper'])))
anchors=[(v['uuid'],mm(v['at_nm'])) for v in report['anchors'] if v['uuid'] in set(geometry['grounded'])]
results={}
site_search={}
for ref in report['new_caps']:
    at=mm(report['lands'][ref]['at_nm'])
    width=.3 if ref=='C470' else .6
    roi=surface.intersection(Point(at).buffer(3.4))
    # Rounded coordinates must not falsely close a tangent contact.
    inside=prep(roi.buffer(-width/2-.001))
    local=[(uid,xy) for uid,xy in anchors if math.dist(at,xy)<=2.4]
    step=.05
    def mmpt(ij):return round(at[0]+ij[0]*step,5),round(at[1]+ij[1]*step,5)
    if not inside.covers(Point(at)):
        results[ref]=dict(width_mm=width,reason='pad centre outside full-width copper',reachable=[]);continue
    pending=[(0,(0,0))];best={(0,0):0};segments={};reached={}
    while pending:
        d,node=heapq.heappop(pending)
        if d!=best[node]:continue
        xy=mmpt(node)
        for identifier,target in local:
            final=math.dist(xy,target)
            if final>.072 or d+final>2.4 or not inside.covers(LineString([xy,target])):continue
            reached[identifier]=min(d+final,reached.get(identifier,math.inf))
        for i,j in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            nxt=node[0]+i,node[1]+j;distance=d+step*math.hypot(i,j)
            if distance>2.4 or distance>=best.get(nxt,math.inf):continue
            key=tuple(sorted((node,nxt)))
            if key not in segments:segments[key]=inside.covers(LineString([xy,mmpt(nxt)]))
            if not segments[key]:continue
            best[nxt]=distance;heapq.heappush(pending,(distance,nxt))
    site_search[ref]=[(*mmpt(node),distance) for node,distance in best.items()]
    results[ref]=dict(width_mm=width,reachable=sorted((dict(uuid=uid,path_mm=dist) for uid,dist in reached.items()),key=lambda r:r['path_mm']),cells=len(best))
output=dict(board_sha256=report['sha256'],search_limit_mm=2.4,grid_mm=.05,geometry_margin_mm=.001,capacitors=results,qualified=all(len(v['reachable'])>=2 for v in results.values()) and bool(results),assembly_ready=False)
(root/'rotated-buck-plane-paths.json').write_text(json.dumps(output,indent=2)+'\n')
if '--sites' in sys.argv:
    Path(sys.argv[sys.argv.index('--sites')+1]).write_text(json.dumps(site_search))
print([(k,len(v['reachable'])) for k,v in results.items()])
