#!/usr/bin/env python3
"""Place previously unrouted USB threshold-divider resistors closer to U24.
Conservative bbox screening; subsequent KiCad DRC is mandatory. No power routing.
"""
from pathlib import Path
import json, math
import pcbnew as p
R=Path(__file__).resolve().parents[1]/'migration-rk3562'
path=R/'kicad/pcb/phoenix-g1.kicad_pcb'
b=p.LoadBoard(str(path));fps={f.GetReference():f for f in b.GetFootprints()}
def pos(item):return (p.ToMM(item.GetPosition().x),p.ToMM(item.GetPosition().y))
def box(item,margin=0):
 q=item.GetBoundingBox()
 return (p.ToMM(q.GetX())-margin,p.ToMM(q.GetY())-margin,p.ToMM(q.GetRight())+margin,p.ToMM(q.GetBottom())+margin)
def overlap(a,z):return a[0]<z[2] and a[2]>z[0] and a[1]<z[3] and a[3]>z[1]
records=[]
for ref,target_ref,pin in [('R1904','U24','15'),('TP13','U15','6')]:
 f=fps[ref];old=pos(f);target=pos(next(a for a in fps[target_ref].Pads() if a.GetNumber()==pin))
 if ref=='R1902':f.SetOrientationDegrees(90)
 # Do not move any pad that already has copper attached, including a shared rail.
 b.BuildConnectivity()
 assert not any(b.GetConnectivity().GetConnectedTracks(a) for a in f.Pads()),ref+' already routed'
 obstacles=[box(q,.25) for q in b.GetFootprints() if q.GetReference()!=ref and (q.GetLayer()==f.GetLayer() or any(a.GetAttribute()==p.PAD_ATTRIB_PTH for a in q.Pads()))]
 obstacles += [box(t,.30) for t in b.GetTracks() if t.IsOnLayer(f.GetLayer())]
 # Leave space for through-via escapes beside the new power backbone.
 obstacles += [box(t,.50) for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.IsOnLayer(p.In2_Cu)]
 old_conflict=any(overlap(box(f),z) for z in obstacles)
 obstacles += [box(z,.25) for q in b.GetFootprints() for z in q.Zones() if z.GetIsRuleArea() and z.IsOnLayer(f.GetLayer())]
 candidates=[(x*.5,y*.5) for x in range(2,49) for y in range(2,77)]
 candidates.sort(key=lambda xy:(math.dist(xy,target),xy))
 chosen=old
 for xy in candidates:
  if not old_conflict and math.dist(xy,target)>=math.dist(old,target):break
  f.SetPosition(p.VECTOR2I(p.FromMM(xy[0]),p.FromMM(xy[1])))
  q=box(f)
  if q[0]<.5 or q[1]<.5 or q[2]>89.5 or q[3]>39.5:continue
  if not any(overlap(q,z) for z in obstacles):chosen=xy;break
 f.SetPosition(p.VECTOR2I(p.FromMM(chosen[0]),p.FromMM(chosen[1])))
 records.append({'ref':ref,'target_pin':target_ref+'.'+pin,'old_xy_mm':old,'new_xy_mm':chosen,'old_center_to_pin_mm':round(math.dist(old,target),3),'new_center_to_pin_mm':round(math.dist(chosen,target),3)})
p.SaveBoard(str(path),b)
report={'status':'PRELIMINARY PLACEMENT; DRC REQUIRED','moves':records,'limitations':['Distances are component-center to controller-pin distances, not copper lengths.','Divider ground returns, analog routing and interference remain unqualified.'],'production_ready':False}
(R/'review/usb-threshold-placement.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
