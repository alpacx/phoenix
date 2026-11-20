"""Search an eight-direction full-width front power corridor to a relocated R530."""
import json, math, os, hashlib
from pathlib import Path
import pcbnew as p
study = Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base = study/'runs/input-ground-local-002'
source = base/'phy-joint.kicad_pcb'
digest = hashlib.sha256(source.read_bytes()).hexdigest()
assert digest == json.loads((base/'report.json').read_text())['candidate_sha256']
board = p.LoadBoard(str(source))
board.BuildConnectivity()
resistor = board.FindFootprintByReference('R530')
input_net = '+3V3_IO'
output_net = '+3V3_PHY'
import sys
target_ref = sys.argv[1] if len(sys.argv)>1 else 'C515'
assert target_ref in ('C515','C517')
target = board.FindFootprintByReference(target_ref).FindPadByNumber('1').GetPosition()
def mm(position):
    return tuple(round(p.ToMM(x),4) for x in position)
def point(x,y):
    return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def distance(a,b):
    return math.dist(mm(a),mm(b))
sources = set()
connected_ids = {item.m_Uuid.AsString() for item in board.GetConnectivity().GetConnectedItems(resistor.FindPadByNumber('1'))}
for item in board.GetTracks():
    if item.m_Uuid.AsString() not in connected_ids or not item.IsOnLayer(p.F_Cu) or item.GetNetname()!=input_net:
        continue
    for endpoint in (item.GetStart(),item.GetEnd()):
        if distance(endpoint,target)<12:
            sources.add(mm(endpoint))
obstacles = [t for t in board.GetTracks() if t.IsOnLayer(p.F_Cu)]
obstacles.extend(q for f in board.GetFootprints() if f.GetReference()!='R530' for q in f.Pads() if q.IsOnLayer(p.F_Cu))
nearby = [(o.GetNetname(),o.GetEffectiveShape(p.F_Cu)) for o in obstacles if o.GetBoundingBox().Inflate(p.FromMM(15)).Contains(target)]
def clear(a,b,net):
    tr=p.PCB_TRACK(board)
    tr.SetStart(a)
    tr.SetEnd(b)
    tr.SetWidth(p.FromMM(1.05))
    tr.SetLayer(p.F_Cu)
    shape=tr.GetEffectiveShape(p.F_Cu)
    return all(not shape.Collide(other,p.FromMM(.2)) for name,other in nearby if name!=net)

from collections import deque


# Grid spans the local supply, PHY and the neighboring Wi-Fi regulator.
pitch = .25
nodes = {(i,j) for i in range(192,281) for j in range(72,145)}
def loc(node):
    return point(node[0]*pitch,node[1]*pitch)
def adjacent(pos):
    x,y=mm(pos)
    i,j=round(x/pitch),round(y/pitch)
    return ((i+a,j+b) for a in (-1,0,1) for b in (-1,0,1) if (i+a,j+b) in nodes)
parents={}
queue=deque()
for xy in sorted(sources):
    feed=point(*xy)
    for node in adjacent(feed):
        if node not in parents and clear(feed,loc(node),input_net):
            parents[node]=(None,xy)
            queue.append(node)
while queue:
    node=queue.popleft()
    for neighbor in adjacent(loc(node)):
        if neighbor not in parents and clear(loc(node),loc(neighbor),input_net):
            parents[neighbor]=(node,None)
            queue.append(neighbor)
routes=[]
for ix in range(-24,25):
    for iy in range(-24,25):
        center=target+point(ix*pitch,iy*pitch)
        for angle in range(0,360,45):
            rad=math.radians(angle)
            offset=point(.51*math.cos(rad),.51*math.sin(rad))
            end=center+offset
            start=center-offset
            if not any(n in parents for n in adjacent(start)):
                continue
            if distance(end,target)<.9 or not clear(end,target,output_net):
                continue
            for node in adjacent(start):
                if node not in parents or not clear(loc(node),start,input_net):
                    continue
                chain=[mm(start)]
                while node is not None:
                    chain.append(mm(loc(node)))
                    node,feed=parents[node]
                chain.append(feed)
                routes.append(dict(center=mm(center),angle=angle,input_path=list(reversed(chain)),output_end=mm(target)))
                break
report=dict(source_sha256=digest,width_mm=1.05,clearance_mm=.2,grid_mm=pitch,reachable_nodes=len(parents),placements_examined=49*49*8,candidates=routes,assembly_ready=False)
(study/('r530-grid-span.json' if target_ref=='C515' else 'r530-grid-span-c517.json')).write_text(json.dumps(report,indent=2)+'\n')
print(len(parents),len(routes),flush=True)
os._exit(0)
