"""Screen a compact VDC filter/dual resistor placement around the known PMIC escape."""
from pathlib import Path
from itertools import permutations
from functools import lru_cache
import hashlib
import json
import math
import os
import pcbnew as p

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-soc-tx-series.json').read_text())
source=root/meta['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==meta['sha256']
board=p.LoadBoard(str(source))
cluster={name:board.FindFootprintByReference(name) for name in ('C410','R410','R411')}
sense={'C410':'1','R410':'2','R411':'1'}
sense_code=cluster['C410'].FindPadByNumber('1').GetNetCode()
launch=p.VECTOR2I(59450000,3250000)
# Only remove the individual branch ends and the original group's sense traces.
branch_ids={'e368d717-6558-4efc-bde9-454409fb5346','4d30df45-7da8-46e1-aee4-ac886ba88828','32e4042f-2d47-4672-8bb1-2a5349dcf2c0','a58de702-292d-4cee-ae3b-9e57e84f1585','271a02a1-76cb-4f5b-a020-e8d66558e0ce','cd7aab4a-1a87-4a93-8686-33994d0d4d25'}
others=[f for f in board.GetFootprints() if f.GetReference() not in cluster]
items=[t for t in board.GetTracks() if t.GetNetCode()!=sense_code and t.m_Uuid.AsString() not in branch_ids]+[q for f in others for q in f.Pads()]
region=p.BOX2I(p.VECTOR2I(55000000,0),p.VECTOR2I(9000000,8000000))
obs=[(x.GetNetCode(),x.GetEffectiveShape(p.B_Cu),x.GetBoundingBox()) for x in items if x.IsOnLayer(p.B_Cu) and x.GetBoundingBox().Intersects(region)]
holes=[q.GetEffectiveHoleShape() for q in items if isinstance(q,p.PCB_VIA) and q.GetBoundingBox().Intersects(region)]
courts=[f.GetCourtyard(p.B_Cu) for f in others if f.GetLayer()==p.B_Cu and f.GetBoundingBox(False,False).Intersects(region)]
tr=p.PCB_TRACK(board);tr.SetLayer(p.B_Cu);tr.SetWidth(200000)
def clear(shape,code):
    box=shape.BBox(350000)
    return not(any(code!=other and box.Intersects(bb) and shape.Collide(geom,202000) for other,geom,bb in obs) or any(shape.Collide(h,250000) for h in holes))
def segment(a,z):
    tr.SetStart(a);tr.SetEnd(z)
    return clear(tr.GetEffectiveShape(p.B_Cu),sense_code)
@lru_cache(None)
def reach(point):
    q=p.VECTOR2I(*point)
    if segment(launch,q):return [tuple(launch),point]
    # Limit the high-impedance branch to a 6 mm detour around the supply lands.
    for x in range(565,626,2):
        for y in range(13,66,2):
            mid=p.VECTOR2I(x*100000,y*100000)
            if math.dist(tuple(launch),tuple(mid))+math.dist(tuple(mid),point)>6000000:continue
            if segment(launch,mid) and segment(mid,q):return [tuple(launch),tuple(mid),point]
    return None
def places(name):
    f=cluster[name];q=f.FindPadByNumber(sense[name]);positions={}
    for angle in (0,90,180,270):
        f.SetOrientationDegrees(angle)
        for x in range(565,626,2):
            for y in range(11,66,2):
                pos=p.VECTOR2I(x*100000,y*100000)
                f.SetPosition(pos)
                court=f.GetCourtyard(p.B_Cu)
                if not court.OutlineCount() or any(court.Collide(other,100000) for other in courts):continue
                if not all(clear(pin.GetEffectiveShape(p.B_Cu),pin.GetNetCode()) for pin in f.Pads()):continue
                point=tuple(q.GetPosition())
                positions[(x,y,angle)]=point
    return positions
options={name:places(name) for name in cluster}
viable=[]; packed=0
for first,second,third in permutations(cluster):
    A,B,C=(options[n] for n in (first,second,third))
    for (x,y,angle),a in A.items():
        # Same orientation of the sense pad. R410 has an opposite sense terminal.
        flip=lambda n: (180 if n=='R410' else 0)
        norm=(angle+flip(first))%360
        for sign in (-1,1):
            dx=0 if norm in (0,180) else sign*12
            dy=sign*12 if dx==0 else 0
            kb=(x+dx,y+dy,(norm-flip(second))%360);kc=(x+2*dx,y+2*dy,(norm-flip(third))%360)
            if kb not in B or kc not in C:continue
            packed+=1
            v=[p.VECTOR2I(*xy) for xy in (a,B[kb],C[kc])]
            if not segment(v[0],v[1]) or not segment(v[1],v[2]):continue
            for i,q in enumerate(v):
                path=reach(tuple(q))
                if not path:continue
                viable.append(dict(placements=dict(zip((first,second,third),[(x,y,angle),kb,kc])),launch_length_mm=sum(math.dist(a,b) for a,b in zip(path,path[1:]))/1e6,path_nm=path,tapped=(first,second,third)[i]))
viable.sort(key=lambda row:row['launch_length_mm'])
result=dict(parent_sha256=meta['sha256'],adopted=False,step_mm=.2,spacing_mm=1.2,search_origin_tenths_mm=True,screened_single={k:len(rows) for k,rows in options.items()},three_component_packings=packed,viable_bus_and_one_bend_landing=len(viable),options=viable[:10])
(root/'pmic-divider-cluster-placement.json').write_text(json.dumps(result,indent=2)+'\n')
print(result,flush=True);os._exit(0)
