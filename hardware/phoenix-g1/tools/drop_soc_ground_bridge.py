"""Search a short ground-plane drop along the newly joined C1609/C1618 return."""
from pathlib import Path
import hashlib,json,math,shutil,subprocess
import pcbnew as p
from pcb_power_leg import make,barrel
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
r=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
cp=json.loads((r/'layout-ground-surface-bends.json').read_text());src=r/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
q=b.FindFootprintByReference('C1609').FindPadByNumber('2');code=q.GetNetCode()
uids={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(q)}
traces=[t for t in b.GetTracks() if t.m_Uuid.AsString() in uids and not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.B_Cu]
region=inflated_box(q,5500000);objects=[o for o in [*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())] if region.Intersects(o.GetBoundingBox())]
layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
lands=[(o.GetBoundingBox(),o.GetEffectiveShape(o.GetParentFootprint().GetLayer())) for o in objects if isinstance(o,p.PAD)]
foreign=[(o.GetBoundingBox(),o.GetEffectiveShape(l),l) for o in objects for l in layers if o.GetNetCode()!=code and o.IsOnLayer(l)]
holes=[(o.GetBoundingBox(),o.GetEffectiveHoleShape()) for o in objects if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
zones=[z.Outline() for z in [*b.Zones(),*(z for f in b.GetFootprints() for z in f.Zones())] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
planes=[next(z.GetFilledPolysList(l) for z in b.Zones() if z.GetNetCode()==code and z.HasFilledPolysForLayer(l)) for l in (p.In1_Cu,p.In4_Cu)]
seeds=[]
for t in traces:
    a,z=tuple(t.GetStart()),tuple(t.GetEnd());n=max(1,math.ceil(t.GetLength()/100000))
    seeds.extend(tuple(round(u+(v-u)*i/n) for u,v in zip(a,z)) for i in range(n+1))
candidates=[]
for x in range(43000000,48500001,50000):
 for y in range(15000000,22000001,50000):
    pos=(x,y);near=min(seeds,key=lambda pt:math.dist(pos,pt))
    if math.dist(pos,near)>2100000:continue
    v=barrel(b,pos,code);vb=inflated_box(v,300000);sh=v.GetEffectiveShape(p.F_Cu)
    if any(vb.Intersects(box) and sh.Collide(s,100000) for box,s in lands) or any(vb.Intersects(box) and sh.Collide(h,252000) for box,h in holes):continue
    if any(vb.Intersects(box) and sh.Collide(s,202000) for box,s,l in foreign) or any(z.Collide(sh,0) for z in zones) or not all(pl.Contains(v.GetPosition()) for pl in planes):continue
    for a in sorted(seeds,key=lambda pt:math.dist(pos,pt)):
        if math.dist(pos,a)>2100000:break
        track=make(b,a,pos,250000,code,p.B_Cu);bb=inflated_box(track,300000);sh=track.GetEffectiveShape(p.B_Cu)
        if any(l==p.B_Cu and bb.Intersects(box) and sh.Collide(s,202000) for box,s,l in foreign) or any(bb.Intersects(box) and sh.Collide(h,252000) for box,h in holes):continue
        candidates.append((math.dist(pos,a),a,pos));break
report=dict(parent_sha256=cp['sha256'],count=len(candidates),closest=sorted(candidates)[:4])
(r/'ground-bridge-plane-window.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
