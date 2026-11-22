"""Explore C421 and L402 together while retaining the currently routed BUCK1/2 input copper."""
from collections import Counter
from pathlib import Path
from itertools import product
import hashlib,json,math,sys
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((r/'layout-npu-c434-paired-load.json').read_text());src=r/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();side=p.F_Cu;V=lambda x:p.VECTOR2I(*x);uid=lambda x:x.m_Uuid.AsString()
c=b.FindFootprintByReference('C421');l=b.FindFootprintByReference('L402');q=b.FindFootprintByReference('U4').FindPadByNumber('9');center=tuple(q.GetPosition());cb=tuple(c.GetPosition());box=inflated_box(q,7000000)
existing={x.GetNumber():[uid(t) for t in b.GetConnectivity().GetConnectedTracks(x)] for x in c.Pads()}
rebuild='--restore-input-return' in sys.argv
old_return='dbd95bb7-1bfc-4d83-8e97-00dcb227e67b'
if rebuild:assert existing['2']==[old_return]
parts=[f for f in b.GetFootprints() if f.GetReference() not in ('C421','L402') and box.Intersects(f.GetBoundingBox())];courts=[f.GetCourtyard(side) for f in parts if f.GetLayer()==side]
obj=[t for t in [*b.GetTracks(),*(x for f in parts for x in f.Pads())] if box.Intersects(t.GetBoundingBox()) and (not rebuild or uid(t)!=old_return)]
foil=[(uid(t),t.GetNetCode(),t.GetEffectiveShape(side),t.GetBoundingBox()) for t in obj if t.IsOnLayer(side)]
holes=[(uid(t),t.GetEffectiveHoleShape(),t.GetPosition()) for t in obj if isinstance(t,p.PCB_VIA) or isinstance(t,p.PAD) and t.GetDrillSize().x]
name={uid(t):(t.GetParentFootprint().GetReference()+'.'+t.GetNumber() if isinstance(t,p.PAD) else t.GetNetname()) for t in obj}
def conflicts(t):
    sh=t.GetEffectiveShape(side);bounds=inflated_box(t,450000)
    return {u for u,n,s,bb in foil if n!=t.GetNetCode() and bounds.Intersects(bb) and sh.Collide(s,202000)}|{u for u,h,xy in holes if bounds.Contains(xy) and sh.Collide(h,252000)}
def solid(f):return not any(f.GetCourtyard(side).Collide(k,100000) for k in courts)
possible=[];near=[];stats=Counter();trunk_barriers=Counter();trunk_examples={}
for angle in (0,90,180,270):
 l.SetOrientationDegrees(angle);sw=l.FindPadByNumber('1')
 for i,j in product(range(-16,17),range(-16,17)):
    at=(center[0]+i*200000,center[1]+j*200000);l.SetPosition(V(at));target=tuple(sw.GetPosition())
    if math.dist(center,target)>3000000 or not solid(l):continue
    stats['L_courtyard']+=1
    blocked=set().union(*(conflicts(x) for x in l.Pads()))
    if blocked:
        near.append((len(blocked),at,angle,sorted(blocked)));continue
    stats['L_lands']+=1
    # Existing .20 mm neck and .60 mm switch-trace criteria, on F.Cu only.
    for nk in (200000,300000,400000,500000):
        toe=(center[0]-320000,center[1]);end=(toe[0]-nk,toe[1])
        for bend in [(target[0],end[1]),(end[0],target[1]),None]:
            pts=[end]+([bend] if bend else [])+[target]
            spans=[make(b,toe,end,200000,q.GetNetCode(),side)]+[make(b,a,z,600000,q.GetNetCode(),side) for a,z in zip(pts,pts[1:]) if a!=z]
            blocked=tuple(sorted(set().union(*(conflicts(t) for t in spans))))
            if blocked:
                trunk_barriers[blocked]+=1
                trunk_examples.setdefault(blocked,(at,angle,nk))
                continue
            if any(t.GetEffectiveShape(side).Collide(l.FindPadByNumber('2').GetEffectiveShape(side),202000) for t in spans):continue
            possible.append((at,angle,[(tuple(t.GetStart()),tuple(t.GetEnd()),t.GetWidth()) for t in spans]));break
        else:continue
        break
candidates=[]
for i,j in product(range(-12,13),range(-12,13)):
 at=(cb[0]+i*100000,cb[1]+j*100000);c.SetPosition(V(at))
 if not solid(c) or any(conflicts(x) for x in c.Pads()):continue
 retained={}
 for x in c.Pads():
    retained[x.GetNumber()]=[u for u,n,s,bb in foil if u in existing[x.GetNumber()] and x.GetEffectiveShape(side).Collide(s,0)]
 if rebuild:
    orig=(52100000,9950000);qg=c.FindPadByNumber('2');a=tuple(qg.GetPosition())
    if not retained['1'] or math.dist(a,orig)>1600000:continue
    ground_leg=make(b,a,orig,300000,qg.GetNetCode(),side)
    if conflicts(ground_leg) or ground_leg.GetEffectiveShape(side).Collide(c.FindPadByNumber('1').GetEffectiveShape(side),202000):continue
 elif any(not group for group in retained.values()):continue
 stats['C_poses_retaining_both_nets']+=1
 for pt,angle,spans in possible:
    l.SetOrientationDegrees(angle);l.SetPosition(V(pt))
    if c.GetCourtyard(side).Collide(l.GetCourtyard(side),100000):continue
    if rebuild and any(ground_leg.GetEffectiveShape(side).Collide(x.GetEffectiveShape(side),202000) for x in l.Pads()):continue
    if any(make(b,a,z,width,q.GetNetCode(),side).GetEffectiveShape(side).Collide(x.GetEffectiveShape(side),202000) for a,z,width in spans for x in c.Pads()):continue
    candidates.append(dict(C421=at,L402=pt,angle=angle,spans=spans,retained=retained))
best=sorted(near,key=lambda n:n[0])[:5]
(r/('gpu-switch-input-rebuilt-return.json' if rebuild else 'gpu-switch-input-paired-placement.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],stats=stats,switch_geometries=len(possible),simultaneous=len(candidates),examples=candidates[:4],best_trunk_conflicts=[dict(blocks=[(u,name[u]) for u in k],count=v,example=trunk_examples[k]) for k,v in sorted(trunk_barriers.items(),key=lambda k:(len(k[0]),-k[1]))[:5]],best_land_conflicts=[dict(at=a,angle=an,obstacles=[(u,name[u]) for u in blocked]) for _,a,an,blocked in best]),indent=2)+'\n')
print(stats,len(possible),len(candidates),[(m,[name[u] for u in b0]) for m,_,_,b0 in best[:2]])
