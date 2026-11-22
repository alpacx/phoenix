"""Test C431 on the populated face along the adopted L401-to-C441 output track."""
from pathlib import Path
import json,hashlib,math,sys
from collections import Counter
import pcbnew as p
from pcb_power_leg import make,barrel
from pcb_bounds import inflated_box
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
npu='--npu' in sys.argv;capref='C434' if npu else 'C431'
base=json.loads((r/('layout-logic-c431-paired-load.json' if npu else 'layout-npu-output-cap-c444.json')).read_text());src=r/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();cap=b.FindFootprintByReference(capref);positive,ret=[cap.FindPadByNumber(n) for n in ('1','2')];rear='--rear' in sys.argv;side=p.B_Cu if rear else p.F_Cu
uid=lambda t:t.m_Uuid.AsString()
def island(f,n):return {uid(x) for x in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference(f).FindPadByNumber(n))}
pid=island('L404' if npu else 'L401','2');gid=island('U4','69')
if cap.GetLayer()!=side:cap.Flip(cap.GetPosition(),False)
start=(71000000,10500000);cap.SetPosition(p.VECTOR2I(*start));box=inflated_box(cap,7500000)
if rear:
    anchor_doc=json.loads((r/('npu-output-source-face-anchors.json' if npu else 'logic-output-source-face-anchors.json')).read_text());assert anchor_doc['parent_sha256']==base['sha256']
    sites=[tuple(row['pt_nm']) for row in anchor_doc['source']]
    front_length={tuple(row['pt_nm']):sum(math.dist(a,b) for a,b in zip(row['route_nm'],row['route_nm'][1:])) for row in anchor_doc['source']}
    start=tuple(round(sum(a[i] for a in sites)/len(sites)) for i in (0,1))
    cap.SetPosition(p.VECTOR2I(*start));box=inflated_box(cap,11000000)
parts=[f for f in b.GetFootprints() if f.GetReference()!=capref and box.Intersects(f.GetBoundingBox())]
courts=[f.GetCourtyard(side) for f in parts if f.GetLayer()==side];objs=[o for o in [*b.GetTracks(),*(q for f in parts for q in f.Pads())] if box.Intersects(o.GetBoundingBox())]
pwr=[];gnd=[]
for o in objs:
    if not o.IsOnLayer(side):continue
    if uid(o) in pid and isinstance(o,p.PCB_TRACK) and not isinstance(o,p.PCB_VIA) and o.GetWidth()>=800000:
        a,z=tuple(o.GetStart()),tuple(o.GetEnd());n=max(1,math.ceil(math.dist(a,z)/200000));pwr.extend(tuple(round(x+(y-x)*i/n) for x,y in zip(a,z)) for i in range(n+1))
    if uid(o) in gid and isinstance(o,p.PCB_VIA) and o.GetDrillValue()>=300000:gnd.append(tuple(o.GetPosition()))
if rear:pwr=sites
foil=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in objs if o.IsOnLayer(side)]
holes=[(o.GetNetCode(),o.GetEffectiveHoleShape(),o.GetPosition()) for o in objs if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
vias=[(o.GetEffectiveShape(side),o.GetBoundingBox()) for o in objs if isinstance(o,p.PCB_VIA)]
def clear(o):
    sh=o.GetEffectiveShape(side);bb=inflated_box(o,450000)
    return not(any(n!=o.GetNetCode() and bb.Intersects(bounds) and sh.Collide(s,202000) for n,s,bounds in foil) or any((isinstance(o,p.PAD) or n!=o.GetNetCode()) and bb.Contains(loc) and sh.Collide(h,252000) for n,h,loc in holes))
cs=Counter();res=[]
positions={((x//100000+i)*100000,(y//100000+j)*100000) for x,y in pwr for i in range(-18,19,2) for j in range(-18,19,2)} if rear else {(start[0]+i*200000,start[1]+j*200000) for i in range(-26,27) for j in range(-20,21)}
for angle in (0,90,180,270):
 cap.SetOrientationDegrees(angle)
 for at in sorted(positions):
    cap.SetPosition(p.VECTOR2I(*at))
    if any(cap.GetCourtyard(side).Collide(other,100000) for other in courts):continue
    cs['courtyard']+=1
    if not all(clear(q) for q in (positive,ret)):continue
    if any(inflated_box(q,150000).Intersects(bb) and q.GetEffectiveShape(side).Collide(sh,100000) for q in (positive,ret) for sh,bb in vias):continue
    cs['lands']+=1
    paths=[]
    branches=[(positive,ret,pwr,2400000),(ret,positive,gnd,1500000)]
    for q,other,targets,limit in (branches[::-1] if npu else branches):
        records=[]
        for goal in targets:
            a=tuple(q.GetPosition())
            if math.dist(a,goal)>limit:continue
            if rear and q.GetNumber()=='1':
                landing=barrel(b,goal,q.GetNetCode(),650000,300000).GetEffectiveShape(side)
                if any(landing.Collide(land.GetEffectiveShape(side),100000) for land in (positive,ret)):continue
            t=make(b,a,goal,800000,q.GetNetCode(),side)
            if clear(t) and not t.GetEffectiveShape(side).Collide(other.GetEffectiveShape(side),202000):records.append((t,goal))
        paths.append(records)
        if npu and not records:break
    if npu:
        if len(paths)!=2:continue
        paths.reverse()
    cs['positive_ok']+=bool(paths[0]);cs['return_ok']+=bool(paths[1])
    for t,a in paths[0]:
      for u,z in paths[1]:
        if not t.GetEffectiveShape(side).Collide(u.GetEffectiveShape(side),202000):
            if rear:
                pair=next(((tt,aa) for tt,aa in paths[0] if 800000<=math.dist(a,aa)<=1050000 and not tt.GetEffectiveShape(side).Collide(u.GetEffectiveShape(side),202000)),None)
                if pair and (not npu or max(math.dist(a,z),math.dist(pair[1],z))<=2800000):res.append((round((t.GetLength()+u.GetLength()+pair[0].GetLength()+(front_length[a]+front_length[pair[1]] if npu else 0))/1e6,4),at,angle,[a,pair[1]],z))
            else:res.append((round((t.GetLength()+u.GetLength())/1e6,4),at,angle,a,z))
(r/('npu-output-cap-rear-stitch-placement.json' if npu and rear else 'logic-output-cap-rear-stitch-placement.json' if rear else 'logic-output-cap-face-placement.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],stats=cs,poses=len(res),best=sorted(res)[:8]),indent=2)+'\n');print(cs,len(res))
