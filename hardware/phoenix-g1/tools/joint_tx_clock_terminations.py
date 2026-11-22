"""Trade unused termination footprints while retaining each data-lane source proximity and both pad escapes."""
from pathlib import Path
import json,hashlib,math
from collections import Counter
import pcbnew as p
from pcb_power_leg import make
from pcb_bounds import inflated_box
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';base=json.loads((r/'layout-npu-c434-paired-load.json').read_text());src=r/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
doc=json.loads((r/'interface-copper-edge-candidates.json').read_text());proof=json.loads((r/'rgmii-clock-fixed-branch-reference.json').read_text());assert not any(proof['missing_samples'].values()) and not proof['near_switch_segments'];path=[tuple(k) for k in next(row['found']['path_nm'] for row in doc['rows'] if row['net']=='ETH_TXCLK' and row['found'])][::-1]
V=lambda xy:p.VECTOR2I(*xy);side=p.F_Cu;results=[]
for ref in ('R502','R505'):
 b=p.LoadBoard(str(src));b.BuildConnectivity();u=b.FindFootprintByReference('U1');f=b.FindFootprintByReference('R506');other=b.FindFootprintByReference(ref);former=tuple(other.GetPosition());fa,fz,oa,oz=[fp.FindPadByNumber(n) for fp in (f,other) for n in ('1','2')]
 assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in (fa,fz,oa,oz))
 soc=next(q for q in u.Pads() if q.GetNetCode()==oa.GetNetCode());dist0=math.dist(tuple(soc.GetPosition()),tuple(oa.GetPosition()))
 box=inflated_box(soc,9000000);parts=[g for g in b.GetFootprints() if g.GetReference() not in (ref,'R506') and box.Intersects(g.GetBoundingBox())];courts=[g.GetCourtyard(side) for g in parts if g.GetLayer()==side];objs=[o for o in [*b.GetTracks(),*(q for g in parts for q in g.Pads())] if box.Intersects(o.GetBoundingBox())]
 foil=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in objs if o.IsOnLayer(side)];holes=[(o.GetEffectiveHoleShape(),o.GetPosition()) for o in objs if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x];vias=[(o.GetEffectiveShape(side),o.GetBoundingBox()) for o in objs if isinstance(o,p.PCB_VIA)]
 def clear(o):
    sh=o.GetEffectiveShape(side);bb=inflated_box(o,450000)
    return not(any(c!=o.GetNetCode() and bb.Intersects(bounds) and sh.Collide(s,202000) for c,s,bounds in foil) or any(bb.Contains(pos) and sh.Collide(h,252000) for h,pos in holes) or isinstance(o,p.PAD) and any(bb.Intersects(bounds) and sh.Collide(s,100000) for s,bounds in vias))
 def good(fp):return not any(fp.GetCourtyard(side).Collide(k,100000) for k in courts) and all(clear(q) for q in fp.Pads())
 legs=[make(b,a,z,200000,fa.GetNetCode(),side) for a,z in zip(path,path[1:])];length=0;clock=[];pose_hash=set();stats=Counter()
 for i,pt in enumerate(path):
    if i:length+=legs[i-1].GetLength()
    if length>3200000:break
    for angle in (0,90,180,270):
      f.SetOrientationDegrees(angle);f.SetPosition(V((0,0)));off=tuple(fa.GetPosition())
      for x in range(-3,4):
       for y in range(-3,4):
        at=(pt[0]-off[0]+x*100000,pt[1]-off[1]+y*100000)
        if (at,angle) in pose_hash:continue
        f.SetPosition(V(at))
        if not fa.GetEffectiveShape(side).Collide(V(pt),0):continue
        pose_hash.add((at,angle))
        if good(f) and not any(t.GetEffectiveShape(side).Collide(fz.GetEffectiveShape(side),202000) for t in legs[:i]):clock.append((length,at,angle,i))
 os=[]
 for i in range(-25,26):
  for j in range(-25,26):
   at=former[0]+i*100000,former[1]+j*100000
   for angle in (0,90,180,270):
    other.SetOrientationDegrees(angle);other.SetPosition(V(at));dd=math.dist(tuple(oa.GetPosition()),tuple(soc.GetPosition()))
    if dd>dist0 or not good(other):continue
    os.append((dd,at,angle))
 options=[]
 for length,at,angle,i in clock:
    f.SetOrientationDegrees(angle);f.SetPosition(V(at))
    for dd,xy,an in os:
        other.SetOrientationDegrees(an);other.SetPosition(V(xy))
        if f.GetCourtyard(side).Collide(other.GetCourtyard(side),100000):continue
        if any(t.GetEffectiveShape(side).Collide(q.GetEffectiveShape(side),202000) for t in legs[:i] for q in other.Pads()):continue
        options.append((length/1e6,dd/1e6,at,angle,xy,an,i))
 results.append(dict(ref=ref,old_source_distance_mm=dist0/1e6,clock_poses=len(clock),alternate_poses=len(os),paired=len(options),best=sorted(options)[:20]))
(r/'rgmii-tx-joint-termination-poses.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],results=results),indent=2)+'\n');print([(q['ref'],q['clock_poses'],q['alternate_poses'],q['paired']) for q in results])
