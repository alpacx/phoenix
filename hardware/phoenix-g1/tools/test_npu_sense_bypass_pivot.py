"""Resolve the one C454 slot depending on C1644, while preserving C1644's own analog bypass."""
import json,math
import pcbnew as p
import place_npu_remote_sense_pair as study
from pcb_power_leg import make
from pcb_bounds import inflated_box
b=study.b;r=study.r;V=study.V;side=study.side;rc=study.rc
slot,=study.repair_slot
cap=b.FindFootprintByReference('C1644');load=b.FindFootprintByReference('U1').FindPadByNumber('1K2')
qa,qg=[cap.FindPadByNumber(n) for n in ('1','2')];source_ground=tuple(qg.GetPosition());before=math.dist(tuple(qa.GetPosition()),tuple(load.GetPosition()))
old_part={study.uid(q) for q in cap.Pads()}
study.foil=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in study.allobj if o.IsOnLayer(side) and study.uid(o) not in old_part]
for f in rc:
    xy,angle=slot[f.GetReference()];f.SetOrientationDegrees(angle);f.SetPosition(V(xy))
pins=[[f.FindPadByNumber(n) for n in ('1','2')] for f in rc];a,z=[tuple(q.GetPosition()) for q in pins[0]];x,y=[tuple(q.GetPosition()) for q in pins[1]]
paths=[make(b,study.center,a,200000,study.code,side),make(b,a,x,200000,study.code,side),make(b,z,y,200000,study.sense,side)]
pcb_blockers={}
for label,o in [(f.GetReference()+'.'+q.GetNumber(),q) for f in rc for q in f.Pads()]+list(zip(('load-to-R','R-C rail','R-C sense'),paths)):
    sh=o.GetEffectiveShape(side);pcb_blockers[label]=[(other.GetParentFootprint().GetReference()+'.'+other.GetNumber() if isinstance(other,p.PAD) else other.GetNetname()+' '+study.uid(other)) for other in study.allobj if study.uid(other) not in old_part and other.GetNetCode()!=o.GetNetCode() and other.IsOnLayer(side) and sh.Collide(other.GetEffectiveShape(side),202000)]
slot_ok=all(study.clear(o) for o in [*paths,*pins[0],*pins[1]]) and not any(t.GetEffectiveShape(side).Collide(q.GetEffectiveShape(side),202000) for t in paths for pp in pins for q in pp if t.GetNetCode()!=q.GetNetCode())
fixed_courts=[f.GetCourtyard(side) for f in study.parts if f.GetLayer()==side and f.GetReference()!='C1644']+[f.GetCourtyard(side) for f in rc]
res=[]
for angle in (0,90,180,270):
 cap.SetOrientationDegrees(angle);cap.SetPosition(V((0,0)));off=tuple(qg.GetPosition())
 for i in range(-3,4):
  for j in range(-3,4):
    at=source_ground[0]+i*50000-off[0],source_ground[1]+j*50000-off[1];cap.SetPosition(V(at))
    if math.dist(tuple(qa.GetPosition()),tuple(load.GetPosition()))>before:continue
    if any(cap.GetCourtyard(side).Collide(k,100000) for k in fixed_courts):continue
    if not all(study.clear(q) for q in cap.Pads()):continue
    if not qg.HitTest(V((37670000,22150000))):continue
    if any(q.GetEffectiveShape(side).Collide(o.GetEffectiveShape(side),202000) for q in cap.Pads() for o in [*paths,*pins[0],*pins[1]] if q.GetNetCode()!=o.GetNetCode()):continue
    res.append(dict(at=at,angle=angle))
(r/'npu-load-sense-c1644-pivot.json').write_text(json.dumps(dict(parent_sha256=study.base['sha256'],RC_slot=slot,slot_clear_if_C1644_absent=slot_ok,RC_fixed_copper_blockers=pcb_blockers,original_analog_pad_to_ball_mm=before/1e6,pivots=res),indent=2)+'\n')
print(slot_ok,len(res),{k:len(v) for k,v in pcb_blockers.items()})
