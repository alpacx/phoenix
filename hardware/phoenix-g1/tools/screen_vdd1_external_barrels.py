"""Probe tented barrels outside the L405 solder opening with unbroken 0.60 mm copper."""
from collections import Counter
import hashlib
import itertools
import json
import math
import sys
from pathlib import Path
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make

stage=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((stage/'layout-lpddr-vdd1-bank.json').read_text())
src=stage/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));q=b.FindFootprintByReference('L405').FindPadByNumber('2')
pt=lambda a:p.VECTOR2I(*a)
center=tuple(q.GetPosition());code=q.GetNetCode()
via=p.PCB_VIA(b);via.SetWidth(600000);via.SetDrill(300000);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetViaType(p.VIATYPE_THROUGH)
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
near=[o for o in [*b.GetTracks(),*(k for f in b.GetFootprints() for k in f.Pads())] if inflated_box(o,4000000).Contains(q.GetPosition())]
other_shapes=[(o.GetNetname(),layer,o.GetEffectiveShape(layer)) for o in near if o.GetNetCode()!=code for layer in layers if o.IsOnLayer(layer)]
holes=[(o.GetNetname(),o.GetEffectiveHoleShape()) for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
lands=[(o.GetParentFootprint().GetReference()+'.'+o.GetNumber(),o.GetEffectiveShape(o.GetParentFootprint().GetLayer()),max(50000,o.GetSolderMaskExpansion(o.GetParentFootprint().GetLayer()))) for o in near if isinstance(o,p.PAD) and not o.GetDrillSize().x]
zones=[z.Outline() for z in [*b.Zones(),*(z for f in b.GetFootprints() for z in f.Zones())] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
edge=p.SHAPE_POLY_SET();assert b.GetBoardPolygonOutlines(edge,False)
edge.Deflate(555000,p.CORNER_STRATEGY_CHAMFER_ALL_CORNERS,1000)
front=[s for _,l,s in other_shapes if l==p.F_Cu]
wire=make(b,center,center,600000,code,p.F_Cu)
def free(a,z):
    wire.SetStart(pt(a));wire.SetEnd(pt(z));s=wire.GetEffectiveShape(p.F_Cu)
    return not any(s.Collide(o,202000) for o in front) and not any(s.Collide(h,252000) for _,h in holes)
land=q.GetEffectiveShape(p.F_Cu)
anchors=[(center[0]+x,center[1]+y) for x in (-250000,0,250000) for y in (-550000,0,550000) if land.Collide(pt((center[0]+x,center[1]+y)),0)]
cells=json.loads((stage/'runs/lpddr-vdd1-l405-frontier.json').read_text())
positions={(x+dx,y+dy) for layer,x,y in cells if layer==0 for dx in (-50000,-25000,0,25000,50000) for dy in (-50000,-25000,0,25000,50000)}
extended='--bent-leg' in sys.argv
if extended:
    positions.update((center[0]+x*50000,center[1]+y*50000) for x in range(-64,65) for y in range(-22,60) if math.hypot(x,y)<=64)
reuse='--resize-existing' in sys.argv
existing=next(o for o in near if isinstance(o,p.PCB_VIA) and o.GetNetCode()==code and tuple(o.GetPosition())==(57300000,2300000)) if reuse else None
if reuse:
    positions={tuple(existing.GetPosition())}
    holes=[(o.GetNetname(),o.GetEffectiveHoleShape()) for o in near if o.m_Uuid.AsString()!=existing.m_Uuid.AsString() and (isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x)]
legal=[];blocked=Counter()
precheck=Counter()
for xy in sorted(positions):
    if not edge.Contains(pt(xy)):precheck['edge']+=1;continue
    via.SetPosition(pt(xy));copper=via.GetEffectiveShape(p.F_Cu);drill=via.GetEffectiveHoleShape()
    mask_hits=sorted(n for n,s,m in lands if drill.Collide(s,m+100000))
    if mask_hits:precheck['solder opening '+','.join(mask_hits)]+=1;continue
    if any(copper.Collide(h,252000) or drill.Collide(h,252000) for _,h in holes):continue
    if any(z.Collide(copper,0) for z in zones):continue
    bad=frozenset(n for n,l,s in other_shapes if copper.Collide(s,202000) or drill.Collide(s,252000))
    if bad:blocked[tuple(sorted(bad))]+=1;continue
    for a in sorted(anchors,key=lambda v:math.dist(v,xy)):
        dx,dy=xy[0]-a[0],xy[1]-a[1]
        d=min(abs(dx),abs(dy));kx=round(math.copysign(d,dx));ky=round(math.copysign(d,dy))
        bends=(a,(a[0]+kx,a[1]+ky),(xy[0]-kx,xy[1]-ky)) if extended else (a,)
        for bend in bends:
            if free(a,bend) and free(bend,xy):
                legal.append(dict(at_nm=xy,anchor_nm=a,bend_nm=bend,length_mm=(math.dist(a,bend)+math.dist(bend,xy))/1e6))
                break
        else:continue
        break
pairs=[(a,z) for a,z in itertools.combinations(legal,2) if .80e6<=math.dist(a['at_nm'],z['at_nm'])<=1.2e6]
(stage/('vdd1-resize-existing-source.json' if reuse else 'vdd1-external-bent-sites.json' if extended else 'vdd1-external-barrel-sites.json')).write_text(json.dumps(dict(parent_sha256=cp['sha256'],tested=len(positions),precheck=precheck,number_clear=len(legal),paired=len(pairs),minimum_edge_to_annulus_mm=.255,assumed_min_mask_expansion_mm=.05,drill_to_opening_margin_mm=.10,trace_width_mm=.60,barrel_mm=[.60,.30],legal=legal,shortest_pairs=sorted(pairs,key=lambda pair:sum(x['length_mm'] for x in pair))[:12],blocker_distribution=[dict(nets=n,count=c) for n,c in blocked.most_common(12)],assembly_ready=False),indent=2)+'\n')
print(len(positions),len(legal),len(pairs),blocked.most_common(3))
