#!/usr/bin/env python3
"""Conservative courtyard/copper screening for one unrouted bypass footprint."""
import pcbnew as p,json,math
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/system-3v3/pcb'
b=p.LoadBoard(str(D/'placement.kicad_pcb'));f=next(f for f in b.GetFootprints() if f.GetReference()=='C1301')
def box(item,layer=None):
 q=item.GetBoundingBox() if layer is None else item.GetBoundingBox(layer)
 return tuple(p.ToMM(v) for v in [q.GetX(),q.GetY(),q.GetRight(),q.GetBottom()])
def overlap(a,z,margin=0):
 return a[0]<z[2]+margin and a[2]>z[0]-margin and a[1]<z[3]+margin and a[3]>z[1]-margin
def segment_hits(a,z,bb,r):
 lo,hi=0.,1.;bb=(bb[0]-r,bb[1]-r,bb[2]+r,bb[3]+r)
 for i in range(2):
  delta=z[i]-a[i]
  if abs(delta)<1e-10:
   if a[i]<bb[i] or a[i]>bb[i+2]:return False
  else:
   u,v=(bb[i]-a[i])/delta,(bb[i+2]-a[i])/delta
   lo=max(lo,min(u,v));hi=min(hi,max(u,v))
   if lo>hi:return False
 return True
obstacles={}
for layer,cl in [(p.F_Cu,p.F_CrtYd),(p.B_Cu,p.B_CrtYd)]:
 courts=[];pads=[];tracks=[]
 for other in b.GetFootprints():
  if other==f:continue
  courts.extend(box(q) for q in other.GraphicalItems() if q.GetLayer()==cl)
  pads.extend((q.GetNetname(),box(q,layer)) for q in other.Pads() if q.IsOnLayer(layer))
 for t in b.GetTracks():
  if t.IsOnLayer(layer):
   a=(p.ToMM(t.GetStart().x),p.ToMM(t.GetStart().y));z=(p.ToMM(t.GetEnd().x),p.ToMM(t.GetEnd().y))
   tracks.append((t.GetNetname(),a,z,p.ToMM(t.GetWidth(layer) if isinstance(t,p.PCB_VIA) else t.GetWidth())/2,isinstance(t,p.PCB_VIA)))
 obstacles[layer]=(courts,pads,tracks)
rows=[]
for layer in [p.F_Cu,p.B_Cu]:
 if f.GetLayer()!=layer:f.Flip(f.GetPosition(),False)
 for angle in [0,90]:
  f.SetOrientationDegrees(angle)
  for ix in range(36,81):
   for iy in range(96,137):
    x,y=ix/4,iy/4;f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)))
    courts,pads,tracks=obstacles[layer]
    own=[box(q) for q in f.GraphicalItems() if q.GetLayer() in [p.F_CrtYd,p.B_CrtYd]]
    if any(overlap(a,z) for a in own for z in courts):continue
    blocked=False
    for q in f.Pads():
     bb=box(q,layer);net=q.GetNetname()
     if any(net!=n and overlap(bb,z,.2) for n,z in pads):blocked=True;break
     if any((net!=n or isvia) and segment_hits(a,z,bb,r+.2) for n,a,z,r,isvia in tracks):blocked=True;break
    if not blocked:
     rows.append({'side':'F' if layer==p.F_Cu else 'B','orientation_deg':angle,'center_mm':[x,y],'distance_to_vin_mm':math.dist((x,y),(13.75,29.1))})
rows.sort(key=lambda r:r['distance_to_vin_mm'])
(D/'input-placement-options.json').write_text(json.dumps({'status':'CONSERVATIVE_SCREEN_REQUIRES_DRC','candidates':rows[:30],'total':len(rows)},indent=2)+'\n')
print(json.dumps(rows[:10],indent=2))
