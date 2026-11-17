#!/usr/bin/env python3
"""Screen front-side L501 placement only; do not mutate the checkpoint or route power."""
import collections,hashlib,json,math
from pathlib import Path
import pcbnew as p
from local_pcb_router import LocalRouter
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
cp=json.loads((D/'working-candidate.json').read_text());src=D/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
fs={f.GetReference():f for f in b.GetFootprints()};f=fs['L501']
assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads())
pin=next(q for q in fs['U5'].Pads() if q.GetNumber()=='30')
if f.GetLayer()!=p.F_Cu:f.Flip(f.GetPosition(),False)
r=LocalRouter(b,(54,20,69,34),grid=.05)
r.pads=[q for q in r.pads if q.GetParentFootprint().GetReference()!='L501']
blocked={q.GetNumber():r.blocked(p.F_Cu,q.GetNetname(),math.hypot(p.ToMM(q.GetSize().x),p.ToMM(q.GetSize().y))) for q in f.Pads()}
obstacles=[(g.GetReference(),g.GetCourtyard(p.F_Cu).BBox()) for g in b.GetFootprints() if g.GetReference()!='L501' and g.GetLayer()==p.F_Cu]
counts=collections.Counter();candidates=[];joint=[]
for x in range(216,277):
 for y in range(80,137):
  for angle in [0,90,180,270]:
   f.SetPosition(p.VECTOR2I(p.FromMM(x/4),p.FromMM(y/4)));f.SetOrientationDegrees(angle)
   sw=next(q for q in f.Pads() if q.GetNumber()=='1')
   distance=math.dist(r.xy(sw),r.xy(pin))
   if distance>5.08:counts['distance']+=1;continue
   box=f.GetCourtyard(p.F_Cu).BBox()
   overlaps=[ref for ref,other in obstacles if box.Intersects(other)]
   if overlaps:
    counts['courtyard']+=1
    if 'U5' not in overlaps:joint.append({'center_mm':[x/4,y/4],'angle_deg':angle,'blocking_refs':overlaps,'pin_to_pad_straight_line_mm':round(distance,4)})
    continue
   if any(r.cell(r.xy(q)) in blocked[q.GetNumber()] for q in f.Pads()):counts['pad_copper']+=1;continue
   if any(row['ref']=='L501' for row in screen(b)):counts['mount_reservation']+=1;continue
   candidates.append({'center_mm':[x/4,y/4],'angle_deg':angle,'pin_to_pad_straight_line_mm':round(distance,4)})
candidates.sort(key=lambda q:q['pin_to_pad_straight_line_mm'])
joint.sort(key=lambda q:(len(q['blocking_refs']),q['pin_to_pad_straight_line_mm']))
unique=[];seen=set()
for row in joint:
 key=tuple(sorted(row['blocking_refs']))
 if key not in seen:unique.append(row);seen.add(key)
report={'status':'PLACEMENT_SCREEN_ONLY' if candidates else 'NO_CANDIDATE_IN_BOUNDED_SCREEN',
 'source_sha256':cp['sha256'],'bounds_mm':[54,20,69,34],'pitch_mm':.25,'candidates':candidates[:20],
 'candidate_count':len(candidates),'joint_review_examples_not_placements':unique[:20],'rejection_counts':dict(counts),'checkpoint_modified':False,
 'limitations':['Conservative raster pad/courtyard screening, not a completed DRC or routed solution.',
 'Distance is a straight-line lower bound; the 5.08 mm screen comes from historical rev 1.1 guidance.',
 'Bulk capacitors, wide copper, return loops, thermal behavior and current remain unqualified.',
 'No accepted placement is written to the PCB.'],'assembly_ready':False}
(D/'pcb/phy-inductor-front-probe.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
