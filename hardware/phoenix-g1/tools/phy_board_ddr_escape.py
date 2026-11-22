"""Find 0.10 mm CPU signal escapes on the populated six-layer candidate with return-plane access."""
from pathlib import Path
from functools import lru_cache
import hashlib
import heapq
import json
import math
import os
import sys
import pcbnew as p
from pcb_bounds import inflated_box, point_distance_squared

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-ground-island-barrels.json').read_text())
src=root/meta['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
b=p.LoadBoard(str(src))
b.BuildConnectivity()
allpads=[q for f in b.GetFootprints() for q in f.Pads()]
allobjs=allpads+list(b.GetTracks())
soc=b.FindFootprintByReference('U1')
rows=[]
layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
vias={t.m_Uuid.AsString() for t in b.GetTracks() if isinstance(t,p.PCB_VIA)}
def route(q,candidates,avoid=()):
    start=q.GetPosition()
    obs={}
    # Batch exact shape tests in a local bounding-box index.
    for l in layers:
        obs[l]=[(k.GetEffectiveShape(l),100000 if k.GetNetname().startswith('LPDDR4_') or isinstance(k,p.PAD) and k.GetParentFootprint().GetReference()=='U1' else 200000,k.GetBoundingBox()) for k in candidates if k.IsOnLayer(l)]
    holes=[k.GetEffectiveHoleShape() for k in candidates if isinstance(k,p.PCB_VIA)]
    t=p.PCB_TRACK(b)
    t.SetWidth(100000)
    t.SetLayer(p.F_Cu)
    v=p.PCB_VIA(b)
    v.SetWidth(450000)
    v.SetDrill(200000)
    v.SetViaType(p.VIATYPE_THROUGH)
    v.SetLayerPair(p.F_Cu,p.B_Cu)
    def free(item,layer):
        box=inflated_box(item,200000)
        shape=item.GetEffectiveShape(layer)
        return not any(box.Intersects(o) and shape.Collide(s,cl) for s,cl,o in obs[layer])
    @lru_cache(None)
    def via_site(i,j):
        pos=start+p.VECTOR2I(i*25000,j*25000)
        if any(math.dist(tuple(pos),other)<225000 for other in avoid):return False
        v.SetPosition(pos)
        if q.GetEffectiveShape(p.F_Cu).Collide(v.GetEffectiveShape(p.F_Cu),100000):return False
        if any(isinstance(k,p.PCB_VIA) and (k.GetPosition()-pos).EuclideanNorm()<max(.20e6+(k.GetDrillValue()+200000)/2, .55e6) for k in candidates):return False
        if any(z.GetIsRuleArea() and z.GetDoNotAllowVias() and inflated_box(z,225000).Contains(pos) for z in b.Zones()):return False
        hole=v.GetEffectiveHoleShape()
        if any(hole.Collide(sh,250000) for l in layers for sh,clear,box in obs[l] if point_distance_squared(box,pos)<500000**2):return False
        if any(v.GetEffectiveShape(p.F_Cu).Collide(h,250000) for h in holes):return False
        return all(free(v,l) for l in layers)
    @lru_cache(None)
    def edge(i,j,x,y):
        t.SetStart(start+p.VECTOR2I(i*25000,j*25000))
        t.SetEnd(start+p.VECTOR2I(x*25000,y*25000))
        return free(t,p.F_Cu) and not any(t.GetEffectiveShape(p.F_Cu).Collide(h,250000) for h in holes)
    cost={(0,0):0}
    queue=[(0,(0,0))]
    parent={}
    end=None
    while queue:
        length,cur=heapq.heappop(queue)
        if length!=cost[cur]:continue
        i,j=cur
        if via_site(i,j):
            end=cur
            break
        if length>2.5e6:continue
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
            nxt=(i+dx,j+dy)
            d=length+math.hypot(dx,dy)*25000
            if d>=cost.get(nxt,math.inf) or not edge(i,j,*nxt):continue
            cost[nxt]=d
            parent[nxt]=cur
            heapq.heappush(queue,(d,nxt))
    pts=[]
    if end is not None:
        while end in parent:
            pts.append(tuple(start+p.VECTOR2I(end[0]*25000,end[1]*25000)))
            end=parent[end]
        pts.append(tuple(start))
        pts.reverse()
    return pts,len(cost)

def virtual(net,points):
    tracks=[]
    c=b.GetNetcodeFromNetname(net)
    for u,z in zip(points,points[1:]):
        t=p.PCB_TRACK(b)
        t.SetNetCode(c)
        t.SetWidth(100000)
        t.SetLayer(p.F_Cu)
        t.SetStart(p.VECTOR2I(*u))
        t.SetEnd(p.VECTOR2I(*z))
        tracks.append(t)
    v=p.PCB_VIA(b)
    v.SetPosition(p.VECTOR2I(*points[-1]))
    v.SetNetCode(c)
    v.SetWidth(450000)
    v.SetDrill(200000)
    v.SetViaType(p.VIATYPE_THROUGH)
    v.SetLayerPair(p.F_Cu,p.B_Cu)
    return tracks+[v]

restore='--restore-neighbor' in sys.argv
if restore:
    test=json.loads((root/'ddr-missing-via-neighbor.json').read_text())
    assert test['source_sha256']==meta['sha256']
    for row in test['rows']:
        if not row['path_nm']:continue
        q=next(q for q in soc.Pads() if q.GetNetname()==row['lifted_copper_net'])
        local=[k for k in allobjs if k.GetNetCode()!=q.GetNetCode() and inflated_box(k,3300000).Contains(q.GetPosition())]
        added=virtual(row['net'],row['path_nm'])
        pts,count=route(q,local+added)
        rows.append(dict(missing=row['net'],missing_path_nm=row['path_nm'],net=q.GetNetname(),restored_ball=q.GetNumber(),visited=count,path_nm=pts))
else:
    for q in soc.Pads():
        if not q.GetNetname().startswith('LPDDR4_'):continue
        if any(k.m_Uuid.AsString() in vias for k in b.GetConnectivity().GetConnectedItems(q)):continue
        start=q.GetPosition()
        candidates=[k for k in allobjs if k.GetNetCode()!=q.GetNetCode() and inflated_box(k,3300000).Contains(start)]
        displaced=['']
        if '--single-neighbor' in sys.argv:
            displaced=sorted({k.GetNetname() for k in candidates if isinstance(k,p.PCB_TRACK) and k.IsOnLayer(p.F_Cu) and k.GetNetname().startswith('LPDDR4_') and inflated_box(k,1200000).Contains(start)})
        fixed=candidates
        for lifted in displaced:
            candidates=[k for k in fixed if not (lifted and k.GetNetname()==lifted and isinstance(k,p.PCB_TRACK))]
            avoid=[]
            for attempt in range(8 if lifted else 1):
                pts,count=route(q,candidates,avoid)
                rows.append(dict(net=q.GetNetname(),ball=q.GetNumber(),lifted_copper_net=lifted,visited=count,path_nm=pts))
                if not pts:break
                avoid.append(pts[-1])
(root/('ddr-restore-neighbor.json' if restore else 'ddr-missing-via-neighbor.json' if '--single-neighbor' in sys.argv else 'ddr-missing-via-escape.json')).write_text(json.dumps(dict(source_sha256=meta['sha256'],width_mm=.1,grid_mm=.025,via_land_drill_mm=[.45,.20],rows=rows,qualified=False),indent=2)+'\n')
print([(r['net'],len(r['path_nm']),r['visited']) for r in rows],flush=True)
os._exit(0)
