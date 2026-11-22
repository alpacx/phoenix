"""Place the 100 Ω / 100 nF parallel sense pair at the already connected SoC bypass node."""
from pathlib import Path
from collections import Counter
import hashlib,json,math,sys
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';base=json.loads((r/'layout-npu-c434-paired-load.json').read_text());src=r/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();V=lambda at:p.VECTOR2I(*at);uid=lambda o:o.m_Uuid.AsString()
gpu='--gpu-pmic' in sys.argv;side=p.F_Cu if gpu else p.B_Cu;names=('R422','C452') if gpu else ('R424','C454');rc=[b.FindFootprintByReference(ref) for ref in names];refpad=b.FindFootprintByReference('U4' if gpu else 'C1621').FindPadByNumber('8' if gpu else '1');center=(55850000,8650000) if gpu else tuple(refpad.GetPosition());code=refpad.GetNetCode();pin_ids=('2','1') if gpu else ('1','2');sense=rc[0].FindPadByNumber(pin_ids[1]).GetNetCode()
assert all(not b.GetConnectivity().GetConnectedTracks(q) for f in rc for q in f.Pads())
box=inflated_box(refpad,7500000);parts=[f for f in b.GetFootprints() if f.GetReference() not in names and box.Intersects(f.GetBoundingBox())]
allobj=[o for o in [*b.GetTracks(),*(q for f in parts for q in f.Pads())] if box.Intersects(o.GetBoundingBox())]
courts=[f.GetCourtyard(side) for f in parts if f.GetLayer()==side];foil=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in allobj if o.IsOnLayer(side)];holes=[(o.GetEffectiveHoleShape(),o.GetPosition()) for o in allobj if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x];via_sh=[(v.GetEffectiveShape(side),v.GetBoundingBox()) for v in allobj if isinstance(v,p.PCB_VIA)];switch=[o.GetEffectiveShape(side) for o in allobj if o.IsOnLayer(side) and o.GetNetname().startswith(('PMIC_SW','CPU_SW','PHY_SW'))]
keep=[z.Outline() for z in [*b.Zones(),*(z for f in parts for z in f.Zones())] if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
def clear(o):
    s=o.GetEffectiveShape(side);bb=inflated_box(o,450000)
    return not(any(n!=o.GetNetCode() and bb.Intersects(g) and s.Collide(k,202000) for n,k,g in foil) or any(bb.Contains(at) and s.Collide(h,252000) for h,at in holes) or any(s.Collide(k,0) for k in keep) or any(s.Collide(k,1000000) for k in switch))
def poses(f):
    if f.GetLayer()!=side:f.Flip(f.GetPosition(),False)
    valid=[];stats=Counter()
    for angle in (0,90,180,270):
        f.SetOrientationDegrees(angle)
        for i in range(-22,23):
         for j in range(-22,23):
            at=(center[0]+i*200000,center[1]+j*200000);f.SetPosition(V(at))
            if any(f.GetCourtyard(side).Collide(o,100000) for o in courts):continue
            stats['body']+=1
            if not all(clear(q) and not any(inflated_box(q,150000).Intersects(g) and q.GetEffectiveShape(side).Collide(s,100000) for s,g in via_sh) for q in f.Pads()):continue
            valid.append((at,angle,*[tuple(f.FindPadByNumber(n).GetPosition()) for n in pin_ids]))
    return valid,stats
rr,rs=poses(rc[0]);cc,cs=poses(rc[1]);counts=Counter();options=[];near=[];single_body=Counter();tap_poses=[];repair_slot=[]
for rp in rr:
 at,ag,a,z=rp;rc[0].SetOrientationDegrees(ag);rc[0].SetPosition(V(at))
 if math.dist(a,center)>3200000:continue
 tap=make(b,center,a,200000,code,side)
 if not clear(tap) or tap.GetEffectiveShape(side).Collide(rc[0].FindPadByNumber(pin_ids[1]).GetEffectiveShape(side),202000):continue
 counts['tap_poses']+=1;tap_poses.append(rp)
 for cp in cc:
    bt,bg,x,y=cp
    gap=max(math.dist(a,x),math.dist(z,y))
    if gap>4000000:continue
    rc[1].SetOrientationDegrees(bg);rc[1].SetPosition(V(bt))
    if rc[0].GetCourtyard(side).Collide(rc[1].GetCourtyard(side),100000):continue
    near.append((gap/1e6,rp,cp))
    if gap>1700000:continue
    counts['body_pairs']+=1
    pwr=make(b,a,x,200000,code,side);fb=make(b,z,y,200000,sense,side)
    if not clear(pwr) or not clear(fb):continue
    if any(v.GetEffectiveShape(side).Collide(fb.GetEffectiveShape(side),202000) for v in (tap,pwr,rc[0].FindPadByNumber(pin_ids[0]),rc[1].FindPadByNumber(pin_ids[0]))) or any(v.GetEffectiveShape(side).Collide(q.GetEffectiveShape(side),202000) for v in (tap,pwr) for q in (rc[0].FindPadByNumber(pin_ids[1]),rc[1].FindPadByNumber(pin_ids[1]))):continue
    options.append(dict(length_mm=sum(v.GetLength() for v in (tap,pwr,fb))/1e6,R424=rp,C454=cp))
for at,angle,a,z in tap_poses:
    rc[0].SetOrientationDegrees(angle);rc[0].SetPosition(V(at))
    for i in range(-8,9):
      for j in range(-8,9):
       for ca in (0,90,180,270):
        xy=at[0]+i*200000,at[1]+j*200000;rc[1].SetOrientationDegrees(ca);rc[1].SetPosition(V(xy));cq=rc[1].GetCourtyard(side)
        if rc[0].GetCourtyard(side).Collide(cq,100000):continue
        if max(math.dist(pt,tuple(rc[1].FindPadByNumber(n).GetPosition())) for n,pt in zip(pin_ids,(a,z)))>1700000:continue
        hits={f.GetReference() for f in parts if f.GetLayer()==side and cq.Collide(f.GetCourtyard(side),100000)}
        if len(hits)==1:single_body.update(hits)
        if hits=={'C1644'}:repair_slot.append(dict(R424=[at,angle],C454=[xy,ca]))
(r/('gpu-pmic-sense-rc-placement.json' if gpu else 'npu-load-sense-rc-placement.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],R_body=rs['body'],R_legal=len(rr),C_body=cs['body'],C_legal=len(cc),screen=counts,nearest_pairs=sorted(near)[:4],individual_body_obstacles=single_body,C1644_relief=repair_slot,solutions=len(options),best=sorted(options,key=lambda v:v['length_mm'])[:6]),indent=2)+'\n');print(rs,len(rr),cs,len(cc),counts,len(options))
