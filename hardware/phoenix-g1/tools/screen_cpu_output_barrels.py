"""Find ordinary through-hole exits directly on the connected wide CPU-output copper."""
from pathlib import Path
from itertools import combinations
import math
import hashlib
import json
import pcbnew as p
from pcb_power_leg import barrel, make
from pcb_bounds import inflated_box

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
state=json.loads((root/"layout-cpu-local-hf-bypass.json").read_text())
path=root/state["board"]
assert hashlib.sha256(path.read_bytes()).hexdigest()==state["sha256"]
board=p.LoadBoard(str(path))
board.BuildConnectivity()
coil=board.FindFootprintByReference("L1001").FindPadByNumber("2")
objects=board.GetConnectivity().GetConnectedItems(coil)
source_ids={item.m_Uuid.AsString() for item in objects}
wide=[t for t in board.GetTracks() if t.m_Uuid.AsString() in source_ids and not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu and t.GetWidth()>=600000]
sites=set()
for t in wide:
    a,b=tuple(t.GetStart()),tuple(t.GetEnd())
    steps=max(1,math.ceil(t.GetLength()/50000))
    sites.update(tuple(round(u+(v-u)*n/steps) for u,v in zip(a,b)) for n in range(steps+1))
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
pads=[q for f in board.GetFootprints() for q in f.Pads()]
neighborhood=inflated_box(coil,8500000)
foreign=[];holes=[];lands=[]
for item in [*board.GetTracks(),*pads]:
    box=item.GetBoundingBox()
    if not neighborhood.Intersects(box):continue
    if isinstance(item,p.PAD):lands.append((box,item.GetEffectiveShape(item.GetParentFootprint().GetLayer())))
    if isinstance(item,p.PCB_VIA) or isinstance(item,p.PAD) and item.GetDrillSize().x:
        holes.append((box,item.GetEffectiveHoleShape()))
    if item.GetNetCode()!=coil.GetNetCode():
        foreign.extend((box,item.GetEffectiveShape(l)) for l in layers if item.IsOnLayer(l))
keepouts=[z.Outline() for z in [*board.Zones(),*(z for f in board.GetFootprints() for z in f.Zones())] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
front_shapes=[(i.GetBoundingBox(),i.GetEffectiveShape(p.F_Cu)) for i in [*board.GetTracks(),*pads] if i.GetNetCode()!=coil.GetNetCode() and i.IsOnLayer(p.F_Cu) and neighborhood.Intersects(i.GetBoundingBox())]
track_zones=[z.Outline() for z in [*board.Zones(),*(z for f in board.GetFootprints() for z in f.Zones())] if z.IsOnLayer(p.F_Cu) and z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
def opening(pos):
    v=barrel(board,pos,coil.GetNetCode())
    v.SetWidth(650000);v.SetDrill(300000)
    shape=v.GetEffectiveShape(p.F_Cu);hole=v.GetEffectiveHoleShape();bb=inflated_box(v,300000)
    if any(bb.Intersects(box) and shape.Collide(sh,100000) for box,sh in lands):return False
    if any(bb.Intersects(box) and shape.Collide(sh,252000) for box,sh in holes):return False
    if any(bb.Intersects(box) and (shape.Collide(sh,202000) or hole.Collide(sh,252000)) for box,sh in foreign):return False
    return not any(z.Collide(shape,0) for z in keepouts)
ok=[pos for pos in sorted(sites) if opening(pos)]
outside={}; extensions={}
pad_seeds=set()
for q in objects:
    if not isinstance(q,p.PAD) or q.GetNetCode()!=coil.GetNetCode() or not q.IsOnLayer(p.F_Cu):continue
    if q.GetParentFootprint().GetReference() not in ("L1001","C1011","C1012","C1013"):continue
    x,y=q.GetPosition();bb=q.GetBoundingBox()
    for dx in range(-bb.GetWidth()//2,bb.GetWidth()//2+1,100000):
        for dy in range(-bb.GetHeight()//2,bb.GetHeight()//2+1,100000):
            pos=(x+dx,y+dy)
            if q.HitTest(p.VECTOR2I(*pos)):pad_seeds.add(pos)
sources=sorted(sites | pad_seeds)
for a in sources:
    for dx,dy in ((0,1),(0,-1),(1,0),(-1,0),(1,1),(-1,-1),(1,-1),(-1,1)):
        for distance in range(200000,1800001,100000):
            end=(a[0]+dx*distance,a[1]+dy*distance)
            line=make(board,a,end,600000,coil.GetNetCode(),p.F_Cu)
            bb=inflated_box(line,300000);sh=line.GetEffectiveShape(p.F_Cu)
            if any(bb.Intersects(box) and sh.Collide(g,202000) for box,g in front_shapes) or any(bb.Intersects(box) and sh.Collide(g,252000) for box,g in holes) or any(z.Collide(sh,0) for z in track_zones):break
            if end not in outside:outside[end]=opening(end)
            if outside[end] and (end not in extensions or math.dist(a,end)<math.dist(extensions[end],end)):extensions[end]=a
extension_pairs=[(a,b) for a,b in combinations(extensions,2) if 850000<=math.dist(a,b)<=1700000]

nearby=[(a,b) for a,b in combinations(ok,2) if 850000<=math.dist(a,b)<=1700000]
best=min(extension_pairs,key=lambda pair:sum(math.dist(q,extensions[q]) for q in pair),default=[])
report=dict(best_pair_nm=[(extensions[q],q) for q in best],parent_sha256=state["sha256"],wide_source_segments=len(wide),tested=len(sites),output_pad_seeds=len(pad_seeds),reachable_extended_sites=len(extensions),extension_pairs=len(extension_pairs),shortest_extensions=sorted(((math.dist(a,z),a,z) for z,a in extensions.items()))[:20],usable_nm=ok,staggered_pairs=nearby,via_diameter_mm=.65,drill_mm=.30)
(root/"cpu-output-existing-copper-vias.json").write_text(json.dumps(report,indent=2)+"\n")
print(len(wide),len(sites),len(ok),len(nearby),len(extensions),len(extension_pairs))
