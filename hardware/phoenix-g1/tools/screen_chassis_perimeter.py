"""Test a jack-bond corridor against physical copper on all six layers."""
from pathlib import Path
from collections import defaultdict
import hashlib,heapq,json,math
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'layout-emmc-data-power.json').read_text());src=root/base['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));jack=b.FindFootprintByReference('J2');pins={n:jack.FindPadByNumber(n) for n in ('P10','SHIELD0','SHIELD1')}
side=p.F_Cu;code=pins['P10'].GetNetCode();layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
uid=lambda o:o.m_Uuid.AsString();V=lambda xy:p.VECTOR2I(*xy)
grid=100000;cell=1000000;idx=defaultdict(list)
def cells(bb):
    return ((i,j) for i in range(bb.GetLeft()//cell,bb.GetRight()//cell+1) for j in range(bb.GetTop()//cell,bb.GetBottom()//cell+1))
for o in [*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())]:
    if o.GetNetCode()==code:continue
    # A single distinct shape per occupied layer. No planes are removed here.
    shapes=[]
    for l in layers:
        if o.IsOnLayer(l):shapes.append(o.GetEffectiveShape(l))
    if not shapes:continue
    ident=o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.GetNetname()+' '+o.GetLayerName()+' '+uid(o)
    for k in cells(inflated_box(o,2700000)):idx[k].append((ident,shapes))
route=make(b,(0,0),(0,0),1000000,code,side)
actual_outline=p.SHAPE_POLY_SET();assert b.GetBoardPolygonOutlines(actual_outline,False)
# Full width plus 0.30 mm clearance to the board contour and any internal cutouts.
inside=p.SHAPE_POLY_SET(actual_outline);inside.Deflate(800000,p.CORNER_STRATEGY_ROUND_ALL_CORNERS,1000)
def hits(xy,margin):
    route.SetStart(V(xy));route.SetEnd(V(xy));shape=route.GetEffectiveShape(side)
    return sorted({name for name,parts in idx[xy[0]//cell,xy[1]//cell] if any(shape.Collide(s,margin) for s in parts)})
def probes(pad):
    at=tuple(pad.GetPosition())
    return [(x*grid,y*grid) for x in range(round(at[0]/grid)-8,round(at[0]/grid)+9) for y in range(round(at[1]/grid)-8,round(at[1]/grid)+9)
            if pad.HitTest(V((x*grid,y*grid)))]
cases=[]
for margin in (2000000,508000):
    # Half a grid diagonal guards all segments, not only raster centers.
    guard=margin+math.ceil(grid/math.sqrt(2))
    ends={n:{xy for xy in probes(q) if not hits(xy,guard) and inside.Contains(V(xy))} for n,q in pins.items()}
    row=dict(margin_mm=margin/1e6,reachable_terminal_cells={n:len(q) for n,q in ends.items()},terminal_nearest={})
    for n,q in pins.items():
        options=[(len(h),h) for pt in probes(q) if inside.Contains(V(pt)) for h in [hits(pt,guard)]]
        row['terminal_nearest'][n]=min(options,default=(0,[]))[1]
    routes=[]
    from functools import lru_cache
    @lru_cache(None)
    def legal(pt):return 65000000<=pt[0]<=90000000 and 7000000<=pt[1]<=33000000 and inside.Contains(V(pt)) and not hits(pt,guard)
    for a,z in [('P10','SHIELD0'),('SHIELD0','SHIELD1')]:
        if not ends[a] or not ends[z]:routes.append(dict(terminals=[a,z],held='blocked terminal land'));continue
        end=ends[z]
        queue=[(0,q) for q in ends[a]];heapq.heapify(queue);parents={q:None for q in ends[a]};cost={q:0 for q in ends[a]};path=[]
        while queue:
            d,at=heapq.heappop(queue)
            if cost.get(at)!=d:continue
            if at in end:
                path=[at]
                while parents[path[-1]] is not None:path.append(parents[path[-1]])
                path.reverse();break
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(-1,1),(1,-1)):
                pt=at[0]+dx*grid,at[1]+dy*grid;new=d+math.hypot(dx,dy)*grid
                if new>=cost.get(pt,math.inf) or not legal(pt):continue
                cost[pt]=new;parents[pt]=at;heapq.heappush(queue,(new,pt))
        routes.append(dict(terminals=[a,z],reachable_states=len(cost),path_nm=path))
    row['routing']=routes;cases.append(row)
(root/'ethernet-chassis-perimeter.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],trace_mm=1,grid_mm=.1,cases=cases,scope='Six-layer projected fixed copper; plane fills omitted only to test best-case future plane removal. A path requires refilled-plane, insulation and EMC checks.',adopted=False),indent=2)+'\n')
print([(c['margin_mm'],c['reachable_terminal_cells'],[(r['terminals'],len(r.get('path_nm',[]))) for r in c['routing']]) for c in cases])
