"""Slide the TX clock termination onto the referenced native escape path, preserving its short source stub."""
from pathlib import Path
import math,json,hashlib
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';base=json.loads((r/'layout-npu-c434-paired-load.json').read_text());src=r/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
native=json.loads((r/'interface-copper-edge-candidates.json').read_text());proof=json.loads((r/'rgmii-clock-fixed-branch-reference.json').read_text());assert base['sha256']==native['parent_sha256']==proof['parent_sha256'];assert sum(proof['missing_samples'].values())==proof['near_switch_segments']==0
full=[tuple(pt) for pt in next(q['found'] for q in native['rows'] if q['net']=='ETH_TXCLK' and q['found'])['path_nm']][::-1]
b=p.LoadBoard(str(src));b.BuildConnectivity();f=b.FindFootprintByReference('R506');assert all(not b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads());pin1,pin2=[f.FindPadByNumber(n) for n in ('1','2')];side=p.F_Cu;V=lambda pt:p.VECTOR2I(*pt);bx=inflated_box(f,8500000)
others=[g for g in b.GetFootprints() if g.GetReference()!='R506' and bx.Intersects(g.GetBoundingBox())];courts=[g.GetCourtyard(side) for g in others if g.GetLayer()==side];objects=[o for o in [*b.GetTracks(),*(q for g in others for q in g.Pads())] if bx.Intersects(o.GetBoundingBox())]
foil=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in objects if o.IsOnLayer(side)];holes=[(o.GetEffectiveHoleShape(),o.GetPosition()) for o in objects if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x];vias=[(o.GetEffectiveShape(side),o.GetBoundingBox()) for o in objects if isinstance(o,p.PCB_VIA)]
def clear(q):
 s=q.GetEffectiveShape(side);box=inflated_box(q,450000);return not (any(q.GetNetCode()!=n and box.Intersects(bb) and s.Collide(k,202000) for n,k,bb in foil) or any(box.Contains(at) and s.Collide(h,252000) for h,at in holes) or any(box.Intersects(bb) and s.Collide(k,100000) for k,bb in vias))
segments=[make(b,a,z,200000,pin1.GetNetCode(),side) for a,z in zip(full,full[1:])];lengths=[0]
for t in segments:lengths.append(lengths[-1]+t.GetLength())
accepted=[];posed=set();gap=[];single={}
for i,pt in enumerate(full):
 for an in (0,90,180,270):
    f.SetOrientationDegrees(an);f.SetPosition(V((0,0)));offset=tuple(pin1.GetPosition())
    for dx in range(-3,4):
     for dy in range(-3,4):
        at=(pt[0]-offset[0]+dx*100000,pt[1]-offset[1]+dy*100000)
        if (at,an) in posed:continue
        f.SetPosition(V(at))
        if not pin1.GetEffectiveShape(side).Collide(V(pt),0):continue
        posed.add((at,an))
        bodies=[g.GetReference() for g in others if g.GetLayer()==side and f.GetCourtyard(side).Collide(g.GetCourtyard(side),100000)]
        if lengths[i]<=3200000 and len(bodies)==1:
            single.setdefault(bodies[0],[]).append(dict(at=at,angle=an,idx=i,length_mm=lengths[i]/1e6))
        if bodies or not clear(pin1) or not clear(pin2):continue
        if any(t.GetEffectiveShape(side).Collide(pin2.GetEffectiveShape(side),202000) for t in segments[:i]):continue
        if i==0:continue
        accepted.append(dict(at=at,angle=an,idx=i,length_mm=lengths[i]/1e6,path_nm=full[:i+1]))
        if lengths[i]<=3200000:gap.append(accepted[-1])
res=dict(parent_sha256=base['sha256'],legal_poses=len(accepted),within_previous_3p2_mm=len(gap),single_body_counts={n:len(ps) for n,ps in single.items()},closest_single_body={n:sorted(ps,key=lambda q:q['length_mm'])[:2] for n,ps in single.items()},best=sorted(accepted,key=lambda q:q['length_mm'])[:7])
(r/'rgmii-clock-source-termination-poses.json').write_text(json.dumps(res,indent=2)+'\n');print(len(accepted),len(gap),res['best'][0]['length_mm'] if accepted else None)
