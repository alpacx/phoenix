"""Find a one-millimetre chassis bond that preserves a two-millimetre projected design corridor."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

if '--extract' in sys.argv:
    import pcbnew as pcb
    from pcb_power_leg import ls
    f,out=sys.argv[-2:]
    b=pcb.LoadBoard(f);jack=b.FindFootprintByReference('J2');code=b.FindNet('CHASSIS').GetNetCode()
    def ring(chain):return [tuple(chain.CPoint(i)) for i in range(chain.PointCount())]
    def polygons(s):
        return [(ring(s.COutline(i)),[ring(s.CHole(i,j)) for j in range(s.HoleCount(i))]) for i in range(s.OutlineCount())]
    obstacles=[];planes=[];terminals={}
    for o in list(b.GetTracks())+[q for fp in b.GetFootprints() for q in fp.Pads()]:
        if o.GetBoundingBox().GetRight()<66000000:continue
        if isinstance(o,pcb.PAD):
            layers=[pcb.F_Cu] if o.IsOnLayer(pcb.F_Cu) else [pcb.B_Cu]
        else:layers=[pcb.F_Cu] if isinstance(o,pcb.PCB_VIA) else [o.GetLayer()]
        for layer in layers:
            shape=pcb.SHAPE_POLY_SET();o.TransformShapeToPolygon(shape,layer,0,1500,pcb.ERROR_OUTSIDE)
            if o.GetNetCode()!=code:obstacles.extend(polygons(shape))
            elif isinstance(o,pcb.PAD) and o.GetParentFootprint().GetReference()=='J2':
                terminals[o.GetNumber()]=dict(at=tuple(o.GetPosition()),polys=polygons(shape))
    for z in b.Zones():
        if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(pcb.B_Cu):
            obstacles.extend(polygons(z.Outline()))
        elif not z.GetIsRuleArea() and z.GetNetCode()!=code:
            for l in ls:
                if z.IsOnLayer(l) and z.HasFilledPolysForLayer(l):
                    planes.append(dict(layer=b.GetLayerName(l),net=z.GetNetname(),polys=polygons(z.GetFilledPolysList(l))))
    edge=pcb.SHAPE_POLY_SET();assert b.GetBoardPolygonOutlines(edge,False)
    Path(out).write_text(json.dumps(dict(obstacles=obstacles,planes=planes,pads=terminals,edge=polygons(edge))));os._exit(0)
import heapq
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import unary_union
from shapely.prepared import prep
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'layout-usb-direction-complete.json').read_text());src=root/base['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
with tempfile.TemporaryDirectory() as tmp:
    out=Path(tmp)/'geometry.json'
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3',__file__,'--extract',str(src),str(out)],capture_output=True,check=True)
    scene=json.loads(out.read_text())
def mm(xy):return tuple(v/1e6 for v in xy)
def geom(rows):
    pieces=[]
    for outer,holes in rows:
        g=Polygon([mm(x) for x in outer],[[mm(x) for x in ring] for ring in holes])
        if not g.is_empty:pieces.append(g if g.is_valid else g.buffer(0))
    return unary_union(pieces)
fixed=geom(scene['obstacles'])
board=geom(scene['edge'])
# Arc approximation and grid both include margin above the exploratory clearance.
domain=board.buffer(-.755).difference(fixed.buffer(2.505))
domain_ready=prep(domain)
pads={k:geom(v['polys']) for k,v in scene['pads'].items()}
def sites(k):
    shape=pads[k]
    # A one-millimetre trace must overlap the annular ring substantially;
    # a hole centre has no bearing on the electrical clearance of the escape.
    outer=shape.buffer(.05).bounds
    return {(i,j) for i in range(math.floor(outer[0]*10),math.ceil(outer[2]*10)+1) for j in range(math.floor(outer[1]*10),math.ceil(outer[3]*10)+1) if shape.covers(Point(i*.1,j*.1)) and domain_ready.covers(Point(i*.1,j*.1))}
def wire(a,z):
    starts=sites(a);goals=sites(z)
    row=dict(pair=[a,z],source_sites=len(starts),target_sites=len(goals))
    if not starts or not goals:return row
    x0,y0=mm(scene['pads'][z]['at'])
    h=lambda xy:math.hypot(xy[0]*.1-x0,xy[1]*.1-y0)
    queue=[(h(x),0,x) for x in starts];heapq.heapify(queue);best=dict.fromkeys(starts,0);parent={}
    while queue:
        _,d,node=heapq.heappop(queue)
        if d!=best[node]:continue
        if node in goals:
            path=[node]
            while path[-1] in parent:path.append(parent[path[-1]])
            path.reverse();xy=[(x*.1,y*.1) for x,y in path]
            line=LineString(xy)
            row.update(path=xy,length_mm=line.length,conductor_clearance_mm=line.distance(fixed)-.5)
            row['plane_overlaps']=[(q['layer'],q['net']) for q in scene['planes'] if geom(q['polys']).intersects(line.buffer(2.5))]
            return row
        for i,j in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            dest=node[0]+i,node[1]+j;nd=d+.1*math.hypot(i,j)
            if not (660<=dest[0]<=900 and 5<=dest[1]<=395) or nd>=best.get(dest,math.inf):continue
            link=LineString([(node[0]*.1,node[1]*.1),(dest[0]*.1,dest[1]*.1)])
            if not domain_ready.covers(link):continue
            prev=best.get(dest);best[dest]=nd;parent[dest]=node;heapq.heappush(queue,(nd+h(dest),nd,dest))
    return row
rows=[wire(a,z) for a,z in [('P10','SHIELD0'),('SHIELD0','SHIELD1')]]
(root/'chassis-projected-routing.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],width_mm=1,projected_clearance_mm=2,results=rows,assembly_ready=False),indent=2)+'\n')
print([(r['pair'],r['source_sites'],r['target_sites'],r.get('length_mm')) for r in rows])
