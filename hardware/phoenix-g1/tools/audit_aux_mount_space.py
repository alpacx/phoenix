#!/usr/bin/env python3
"""Conservative both-side mechanical search; candidates are not drill authorizations."""
import pcbnew as p,json,math,hashlib
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-inputs'
cp=json.loads((D/'working-candidate.json').read_text());src=D/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));radius=2.7
def box(s):
 z=s.GetBoundingBox();return tuple(p.ToMM(v) for v in [z.GetX(),z.GetY(),z.GetRight(),z.GetBottom()])
shapes=[]
for f in b.GetFootprints():
 for s in list(f.Pads())+[g for g in f.GraphicalItems() if g.GetLayer() in [p.F_CrtYd,p.B_CrtYd]]:
  shapes.append((f.GetReference(),box(s)))
def hits(x,y,bb):
 x0,y0,x1,y1=bb
 return math.hypot(max(x0-x,0,x-x1),max(y0-y,0,y-y1))<radius
def dist(x,y,t):
 a,z=t.GetStart(),t.GetEnd();ax,ay,zx,zy=[p.ToMM(v) for v in [a.x,a.y,z.x,z.y]]
 dx,dy=zx-ax,zy-ay;den=dx*dx+dy*dy
 u=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/den)) if den else 0
 return math.hypot(x-ax-u*dx,y-ay-u*dy)
tracks=list(b.GetTracks())
def blockers(x,y):
 refs=sorted({ref for ref,bb in shapes if hits(x,y,bb)})
 copper=[t.m_Uuid.AsString() for t in tracks if dist(x,y,t)<radius+p.ToMM(t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth())/2]
 return refs,copper
rows=[]
for ref,x,y in [('H8103',21,3),('H8104',37,31),('H8105',70,34)]:
 refs,copper=blockers(x,y);rows.append({'ref':ref,'center_mm':[x,y],'component_blockers':refs,'copper_conflicts':len(copper)})
free=[]
# Circle wholly within the desired 85x35 envelope, not proof that the full PCB can shrink.
for ix in range(6,165):
 for iy in range(6,65):
  x,y=ix/2,iy/2
  if any(hits(x,y,bb) for _,bb in shapes):continue
  if any(dist(x,y,t)<radius+p.ToMM(t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth())/2 for t in tracks):continue
  free.append([x,y])
for r in rows:r['nearest_clear_grid_candidates_mm']=sorted(free,key=lambda q:math.dist(q,r['center_mm']))[:5]
report={'status':'GEOMETRIC_SEARCH_NOT_MECHANICAL_QUALIFICATION','source_sha256':cp['sha256'],'reservation_radius_mm':radius,'grid_mm':.5,'auxiliary_mounts':rows,'clear_grid_points':len(free),'limits':['Courtyard and pad bounding boxes are conservative','Zones and enclosure geometry not qualified','No holes or reservations moved','Candidate points can overlap each other; not a simultaneous mounting pattern'],'assembly_ready':False}
(D/'pcb/aux-mount-space.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
