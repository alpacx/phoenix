"""Flood the shared BUCK1/2 input branch and classify via conflicts by actual layer/net."""
from pathlib import Path
from functools import lru_cache
from collections import Counter
import hashlib
import heapq
import json
import math
import os
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
folder=root/'runs/pmic-five-stage-full-coupled-0';src=folder/'phy-joint.kicad_pcb'
j=json.loads((root/'runs/pmic-five-stage-coupled-0/power-paths.json').read_text())
q=next(row for row in j['vcc_taps'] if row['stage']==1);a=tuple(q['terminal_nm']);b=p.LoadBoard(str(src))
movable=('C421','C422')
ls=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu);code=b.FindNet('+3V3_SYS').GetNetCode()
allitems=[x for x in list(b.GetTracks())+[pad for f in b.GetFootprints() if f.GetReference() not in movable for pad in f.Pads()] if inflated_box(x,5200000).Contains(p.VECTOR2I(*a))]
geom={l:[(o,o.GetEffectiveShape(l),o.GetBoundingBox()) for o in allitems if o.IsOnLayer(l) and o.GetNetCode()!=code] for l in ls}
holes=[(o,o.GetPosition(),o.GetEffectiveHoleShape()) for o in allitems if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
zones=list(b.Zones())+[k for f in b.GetFootprints() for k in f.Zones()]
keeps=[q.Outline() for q in zones if q.GetIsRuleArea() and q.IsOnLayer(p.F_Cu) and q.GetDoNotAllowTracks()]
vk=[q.Outline() for q in zones if q.GetIsRuleArea() and q.GetDoNotAllowVias()]
t=p.PCB_TRACK(b);t.SetWidth(500000);t.SetLayer(p.F_Cu);t.SetNetCode(code);via=p.PCB_VIA(b);via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetWidth(450000);via.SetDrill(200000)
def name(o):return o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.m_Uuid.AsString()
def reason(u,v):
    t.SetStart(p.VECTOR2I(*u));t.SetEnd(p.VECTOR2I(*v));s=t.GetEffectiveShape(p.F_Cu);bb=inflated_box(t,370000)
    hit=[(o.GetNetname(),name(o)) for o,g,box in geom[p.F_Cu] if bb.Intersects(box) and s.Collide(g,202000)]
    hit.extend((o.GetNetname(),name(o)) for o,pt,h in holes if o.GetNetCode()!=code and bb.Contains(pt) and s.Collide(h,250000))
    if any(k.Collide(s,0) for k in keeps):hit.append(('keepout',''))
    return hit
def site(pt):
    pxy=p.VECTOR2I(*pt);via.SetPosition(pxy);s=via.GetEffectiveShape(p.F_Cu);h=via.GetEffectiveHoleShape();bb=inflated_box(via,370000)
    hit=set()
    for l in ls:
        for o,g,box in geom[l]:
            if bb.Intersects(box) and (s.Collide(g,202000) or h.Collide(g,250000)):hit.add((o.GetNetname(),name(o),b.GetLayerName(l)))
    for o,xy,h2 in holes:
        if bb.Contains(xy) and h.Collide(h2,250000):hit.add((o.GetNetname(),name(o),'drill'))
    for pad in allitems:
        if isinstance(pad,p.PAD) and pad.GetNetCode()==code and s.Collide(pad.GetEffectiveShape(pad.GetParentFootprint().GetLayer()),50000):hit.add((pad.GetNetname(),name(pad),'land'))
    if any(k.Collide(s,0) for k in vk):hit.add(('keepout','',''))
    return tuple(sorted(hit))
step=50000
@lru_cache(None)
def edge(x,y):return not reason(x,y)
limits={};paths={};queue=[];neutral=[]
for dx,dy in ((0,0),(1,0),(-1,0),(0,1),(0,-1)):
    xy=(round(a[0]/step)*step+dx*step,round(a[1]/step)*step+dy*step)
    if edge(a,xy):limits[xy]=math.dist(a,xy);paths[xy]=a;heapq.heappush(queue,(limits[xy],xy))
while queue:
    length,xy=heapq.heappop(queue)
    if limits[xy]!=length:continue
    hits=site(xy);neutral.append((len({o[1] for o in hits}),length,xy,hits))
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(-1,-1),(1,-1)):
        z=(xy[0]+dx*step,xy[1]+dy*step);nd=length+math.hypot(dx,dy)*step
        if nd<=3500000 and nd<limits.get(z,math.inf) and edge(xy,z):limits[z]=nd;paths[z]=xy;heapq.heappush(queue,(nd,z))
free=[r for r in sorted(neutral) if not r[0]]
pairs=[(a[2],z[2]) for i,a in enumerate(free) for z in free[:i] if 600000<=math.dist(a[2],z[2])<=1050000]
stem=q['lines_nm'][-1]
sp=[]
for i in range(20):
    xy=tuple(round(stem[0][axis]+i/19*(stem[1][axis]-stem[0][axis])) for axis in range(2))
    sp.append(dict(pt_nm=xy,hits=site(xy)))
res=dict(stem_sites=sp,coupon_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),feeder_nm=a,start_obstacles=reason(a,a),front_nodes=len(limits),unblocked_vias=len(free),pair_count=len(pairs),examples=pairs[:8],least_obstructed=sorted(neutral)[:6])
(folder/'shared-feed-window.json').write_text(json.dumps(res,indent=2)+'\n');print(res['front_nodes'],res['unblocked_vias'],[(e['pt_nm'],e['hits']) for e in sorted(sp,key=lambda r:len(r['hits']))[:2]],flush=True);os._exit(0)
