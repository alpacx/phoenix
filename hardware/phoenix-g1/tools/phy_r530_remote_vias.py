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
def flood(seeds,net):
    parents={}
    queue=deque()
    for xy in sorted(seeds):
        feed=point(*xy)
        for node in adjacent(feed):
            if node not in parents and clear(feed,loc(node),net):
                parents[node]=(None,xy)
                queue.append(node)
    while queue:
        node=queue.popleft()
        for neighbor in adjacent(loc(node)):
            if neighbor not in parents and clear(loc(node),loc(neighbor),net):
                parents[neighbor]=(node,None)
                queue.append(neighbor)
    return parents
parents=flood(sources,input_net)
outputs=flood([mm(target)],output_net)

# Screen remote via landings throughout the entire reachable output region.
tracks=list(board.GetTracks())
pads=[q for f in board.GetFootprints() for q in f.Pads()]
near=[o for o in tracks+pads if o.GetBoundingBox().Inflate(p.FromMM(14)).Contains(target)]
locations=[]
for node in sorted(outputs):
    xy=loc(node)
    via=p.PCB_VIA(board)
    via.SetPosition(xy)
    via.SetWidth(p.FromMM(.6))
    via.SetDrill(p.FromMM(.3))
    shape=via.GetEffectiveShape(p.F_Cu)
    blocked=False
    for item in near:
        if isinstance(item,p.PAD):
            if item.GetBoundingBox().Inflate(p.FromMM(.35)).Contains(xy):
                blocked=True
                break
        if item.GetNetname()==output_net:
            continue
        if shape.Collide(item.GetEffectiveShape(item.GetLayer()),p.FromMM(.2)):
            blocked=True
            break
    if not blocked:
        path=[]
        while node is not None:
            path.append(mm(loc(node)))
            node,seed=outputs[node]
        path.append(seed)
        locations.append(dict(xy=mm(xy),path=list(reversed(path))))
report=dict(source_sha256=digest,target=target_ref,reachable_nodes=len(outputs),via_diameter_mm=.6,drill_mm=.3,trace_width_mm=1.05,candidate_landings=locations,assembly_ready=False)
(study/f'r530-remote-vias-{target_ref}.json').write_text(json.dumps(report,indent=2)+'\n')
print(len(outputs),len(locations),flush=True)
os._exit(0)
