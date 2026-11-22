"""Screen new front-side R530 sites with both full-width straight connections."""
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
target = board.FindFootprintByReference('C515').FindPadByNumber('1').GetPosition()
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
sites=0
out_clear=0
routes=[]
bent_routes=[]
for ix in range(-12,13):
    for iy in range(-12,13):
        center=target+point(ix*.5,iy*.5)
        for angle in (0,45,90,135,180,225,270,315):
            sites+=1
            rad=math.radians(angle)
            offset=point(.51*math.cos(rad),.51*math.sin(rad))
            end=center+offset
            start=center-offset
            if distance(end,target)<.9 or not clear(end,target,output_net):
                continue
            out_clear+=1
            for xy in sorted(sources):
                feed=point(*xy)
                if distance(start,feed)>.8 and clear(feed,start,input_net):
                    routes.append(dict(center=mm(center),angle=angle,input_endpoint=xy))
                for corner in (p.VECTOR2I(feed.x,start.y),p.VECTOR2I(start.x,feed.y)):
                    if min(distance(corner,feed),distance(corner,start))<.3:
                        continue
                    if clear(feed,corner,input_net) and clear(corner,start,input_net):
                        bent_routes.append(dict(center=mm(center),angle=angle,input_endpoint=xy,corner=mm(corner)))
report=dict(source_sha256=digest,sites=sites,clear_output=out_clear,source_copper_endpoints=sorted(sources),straight_routes=routes,single_right_angle_routes=bent_routes,width_mm=1.05,clearance_mm=.2,scope='straight output and straight or single orthogonal bend input; placement, source current and DRC require separate qualification')
(study/'r530-direct-span-screen.json').write_text(json.dumps(report,indent=2)+'\n')
print(sites,out_clear,len(sources),len(routes),len(bent_routes),flush=True)
os._exit(0)
