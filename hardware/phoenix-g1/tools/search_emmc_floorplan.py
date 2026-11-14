#!/usr/bin/env python3
"""Search placement, allowing only unrouted passive relocation; not electrical qualification."""
import pcbnew as p, numpy as np, json,math,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/'migration-rk3562/experiments/emmc-system/pcb';m=json.loads((D/'migration.json').read_text());src=D/'emmc-placement.kicad_pcb';b=p.LoadBoard(str(src));original=p.LoadBoard(str(R/m['source_board']));original.BuildConnectivity();old={f.GetReference():f for f in original.GetFootprints()};fs=list(b.GetFootprints());added=set(m['new_backside_positions_mm']);memory=next(f for f in fs if f.GetReference()=='U8001')
def xy(q):return p.ToMM(q.GetPosition().x),p.ToMM(q.GetPosition().y)
def bbox(q):
 r=q.GetBoundingBox();return np.array([p.ToMM(v) for v in [r.GetX(),r.GetY(),r.GetRight(),r.GetBottom()]])
def courtyard(f):
 boxes=[bbox(q) for q in f.GraphicalItems() if q.GetLayer()==p.B_CrtYd]
 if not boxes:return None
 a=np.array(boxes);return np.array([a[:,0].min(),a[:,1].min(),a[:,2].max(),a[:,3].max()])
def overlap(a,z,gap=.15):return a[0]<z[2]+gap and a[2]>z[0]-gap and a[1]<z[3]+gap and a[3]>z[1]-gap
bodies=[];through=[]
for f in fs:
 ref=f.GetReference()
 if ref in added:continue
 box=courtyard(f)
 movable=ref.startswith(('C','R')) and ref in old and not any(original.GetConnectivity().GetConnectedTracks(q) for q in old[ref].Pads())
 if box is not None:bodies.append((ref,box,movable))
 for q in f.Pads():
  if q.GetAttribute() in [p.PAD_ATTRIB_PTH,p.PAD_ATTRIB_NPTH]:through.append(bbox(q))
segments=[]
for t in b.GetTracks():
 if isinstance(t,p.PCB_VIA):
  a=xy(t);z=a;radius=max(p.ToMM(t.GetWidth(p.F_Cu))/2+.2,p.ToMM(t.GetDrillValue())/2+.25)
 elif t.GetLayer()==p.B_Cu:a=(p.ToMM(t.GetStart().x),p.ToMM(t.GetStart().y));z=(p.ToMM(t.GetEnd().x),p.ToMM(t.GetEnd().y));radius=p.ToMM(t.GetWidth())/2+.2
 else:continue
 segments.append((a,z,radius,t.GetNetname(),t.m_Uuid.AsString()))
A=np.array([s[0] for s in segments]);Z=np.array([s[1] for s in segments]);rad=np.array([s[2] for s in segments]);low=np.minimum(A,Z)-rad[:,None]-.3;high=np.maximum(A,Z)+rad[:,None]+.3
reserves=[(53,4),(83,3),(21,3),(37,31),(70,34)];rows=[];checked=0;geometric=0;best=[]
for orientation in [0,90]:
 memory.SetOrientationDegrees(orientation);origin=np.array(xy(memory));offsets=np.array([xy(q) for q in memory.Pads()])-origin;pr=np.array([max(p.ToMM(q.GetSize().x),p.ToMM(q.GetSize().y))/2 for q in memory.Pads()]);cb=courtyard(memory)-np.tile(origin,2)
 for x in np.arange(6.5,79,.5):
  for y in np.arange(6.5,29,.5):
   checked+=1;center=np.array([x,y]);box=cb+np.tile(center,2)
   if min(box[:2])<.5 or box[2]>84.5 or box[3]>34.5:continue
   if any(math.hypot(max(box[0]-mx,0,mx-box[2]),max(box[1]-my,0,my-box[3]))<2.7 for mx,my in reserves):continue
   conflicts=[(ref,movable) for ref,other,movable in bodies if overlap(box,other)]
   if any(not movable for _,movable in conflicts) or any(overlap(box,q,.3) for q in through):continue
   geometric+=1;points=offsets+center;mn=points.min(axis=0)-.3;mx=points.max(axis=0)+.3;idx=np.where(np.all(high>=mn,axis=1)&np.all(low<=mx,axis=1))[0]
   collision=[]
   if len(idx):
    aa=A[idx];dd=Z[idx]-aa;den=(dd*dd).sum(axis=1);delta=points[:,None,:]-aa[None,:,:];t=np.divide((delta*dd[None,:,:]).sum(axis=2),den[None,:],out=np.zeros((len(points),len(idx))),where=den[None,:]>0);t=np.clip(t,0,1);dist=np.linalg.norm(delta-t[:,:,None]*dd[None,:,:],axis=2);hit=np.any(dist<pr[:,None]+rad[idx][None,:]+.025,axis=0);collision=[segments[k][3:] for k in idx[hit]]
   rec={'center_mm':[float(x),float(y)],'orientation_degrees':orientation,'passives_to_relocate':[ref for ref,_ in conflicts],'copper_conflicts':[{'net':net,'uuid':uid} for net,uid in collision],'distance_from_soc_mm':round(math.dist(center,(43,20)),3)}
   if not collision:rows.append(rec)
   best.append(rec)
rows.sort(key=lambda r:(len(r['passives_to_relocate']),r['distance_from_soc_mm']))
best.sort(key=lambda r:(len(r['copper_conflicts']),len(r['passives_to_relocate']),r['distance_from_soc_mm']))
report={'status':'GEOMETRIC_SCREEN_NOT_PLACEMENT_QUALIFICATION','source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'target_envelope_mm':[85,35],'grid_mm':.5,'positions_screened':checked,'positions_without_fixed_body_conflicts':geometric,'positions_without_copper_conflicts':len(rows),'top_candidates':rows[:30],'least_conflicted_candidates':best[:10],'existing_copper_fixed':True,'all_positions_exhausted':False,'assembly_ready':False};(D/'emmc-floorplan-search.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k not in ['top_candidates','least_conflicted_candidates']});print(json.dumps(rows[:3] or best[:3],indent=2))
