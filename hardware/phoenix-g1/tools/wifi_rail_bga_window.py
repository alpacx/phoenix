"""Move the existing 1 mm In3 radio supply trunk around the SoC oscillator/USB land projections."""
from functools import lru_cache
from pathlib import Path
import hashlib
import heapq
import json
import math
import os
import shutil
import subprocess
import sys
import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-soc-tx-series.json').read_text());src=root/meta['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
small='--nominal-land' in sys.argv
b=p.LoadBoard(str(src));u=b.FindFootprintByReference('U1');layer=p.In3_Cu
cut={'594c902f-06e9-4485-8852-e229a4c41da2','2350ae70-185d-4248-8e2a-6651b08491d7'}
old=[t for t in b.GetTracks() if t.m_Uuid.AsString() in cut]
assert len(old)==2 and all(t.GetWidth()==1000000 and t.GetLayer()==layer and t.GetNetname()=='+3V58_WIFI' for t in old)
code=old[0].GetNetCode();before=sum(t.GetLength() for t in old)
endpoints=[tuple(v) for t in old for v in (t.GetStart(),t.GetEnd())];start,end=sorted(pt for pt in set(endpoints) if endpoints.count(pt)==1)
for t in old:b.Remove(t)
items=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if o.GetNetCode()!=code and o.IsOnLayer(layer) and inflated_box(o,10000000).Contains(p.VECTOR2I(*start))]
obs=[(o.GetEffectiveShape(layer),o.GetBoundingBox()) for o in items]
holes=[(o.GetEffectiveHoleShape(),o.GetPosition()) for o in items if isinstance(o,p.PCB_VIA)]
reserves=[]
for n in ('AF25','AF26','AE26'):
    v=p.PCB_VIA(b);v.SetWidth(250000 if small else 450000);v.SetDrill(150000 if small else 200000);v.SetPosition(u.FindPadByNumber(n).GetPosition());v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);reserves.append(v)
keep=[z.Outline() for z in list(b.Zones())+[a for f in b.GetFootprints() for a in f.Zones()] if z.GetIsRuleArea() and z.IsOnLayer(layer) and z.GetDoNotAllowTracks()]
t=p.PCB_TRACK(b);t.SetWidth(1000000);t.SetLayer(layer);t.SetNetCode(code)
@lru_cache(None)
def free(a,z):
    t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));s=t.GetEffectiveShape(layer);bb=inflated_box(t,365000)
    return not (any(bb.Intersects(box) and s.Collide(shape,202000) for shape,box in obs) or any(bb.Contains(pos) and s.Collide(h,250000) for h,pos in holes) or any(s.Collide(v.GetEffectiveShape(layer),202000) for v in reserves) or any(k.Collide(s,0) for k in keep))
step=50000
dist={start:0};prev={};queue=[(math.dist(start,end),0,start)]
while queue:
    _,length,at=heapq.heappop(queue)
    if length!=dist[at]:continue
    if at==end:break
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(-1,1),(1,-1)):
        pt=(at[0]+dx*step,at[1]+dy*step);nd=length+step*math.hypot(dx,dy);h=math.dist(pt,end)
        if nd+h>before*1.15 or nd>=dist.get(pt,math.inf) or not free(at,pt):continue
        dist[pt]=nd;prev[pt]=at;heapq.heappush(queue,(nd+h,nd,pt))
result=dict(parent_sha256=meta['sha256'],prior_mm=before/1e6,retained_width_mm=1,sites=['U1.AF25','U1.AF26','U1.AE26'],visited=len(dist),change=False)
if end in dist:
    points=[end]
    while points[-1]!=start:points.append(prev[points[-1]])
    points.reverse();simplified=[points[0]]
    for a,z,w in zip(points,points[1:],points[2:]):
        if (z[0]-a[0],z[1]-a[1])!=(w[0]-z[0],w[1]-z[1]):simplified.append(z)
    simplified.append(end)
    for a,z in zip(simplified,simplified[1:]):
        trace=p.PCB_TRACK(b);trace.SetWidth(1000000);trace.SetNetCode(code);trace.SetLayer(layer);trace.SetStart(p.VECTOR2I(*a));trace.SetEnd(p.VECTOR2I(*z));b.Add(trace)
    folder=root/'runs'/('wifi-rail-small-window' if small else 'wifi-rail-bga-window');folder.mkdir(exist_ok=True)
    for fn in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/fn,folder/fn)
    out=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
    if not delta:
        saved=p.LoadBoard(str(out));pres=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper=cut);assert not screen(saved)
        result.update(change=True,board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),new_mm=dist[end]/1e6,preservation=pres,new_drc=delta)
    else:result['new_drc']=delta
(root/('wifi-rail-small-window.json' if small else 'wifi-rail-bga-window.json')).write_text(json.dumps(result,indent=2)+'\n')
print(result['change'],result.get('new_mm'),result['visited'],flush=True);os._exit(0)
