#!/usr/bin/env python3
"""Conservative all-layer antenna envelope screen; no routing changes."""
import pcbnew as p,json,hashlib,os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=root/'migration-rk3562/experiments/pmic-ldo-inputs/pcb/parallel-local-copper.kicad_pcb'
out=root/'migration-rk3562/experiments/internal-antenna/review'
b=p.LoadBoard(str(source))
def box(q):
 r=q.GetBoundingBox();return [p.ToMM(v) for v in (r.GetX(),r.GetY(),r.GetRight(),r.GetBottom())]
def overlap(a,c):return a[0]<c[2] and a[2]>c[0] and a[1]<c[3] and a[3]>c[1]
# Whole-body bounding boxes are deliberately conservative; include both assembly faces.
fp=[]
for f in b.GetFootprints():
 r=f.GetBoundingBox(False,False);fp.append((f.GetReference(),[p.ToMM(v) for v in (r.GetX(),r.GetY(),r.GetRight(),r.GetBottom())]))
tracks=[(t.m_Uuid.AsString(),t.GetNetname(),box(t)) for t in b.GetTracks()]
candidates=[]
for side in ('top','bottom','left','right'):
 for i in range(76 if side in ('top','bottom') else 26):
  r=[i,0,i+14.15,7.4] if side=='top' else [i,32.6,i+14.15,40] if side=='bottom' else [0,i,7.4,i+14.15] if side=='left' else [82.6,i,90,i+14.15]
  hits=[ref for ref,bb in fp if overlap(r,bb)]
  th=[{'uuid':u,'net':n} for u,n,bb in tracks if overlap(r,bb)]
  candidates.append({'side':side,'box_mm':r,'components':hits,'copper_objects':th,'component_count':len(hits),'copper_count':len(th)})
candidates.sort(key=lambda c:(c['component_count'],c['copper_count']))
data={'source':str(source.relative_to(root)),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'screen':'Conservative rectangular envelope, 1mm edge sweep; not a geometric impossibility proof','status':'RELOCATION_REQUIRED' if all(c['component_count'] or c['copper_count'] for c in candidates) else 'CANDIDATE_REQUIRES_ZONE_AND_MECHANICAL_REVIEW','zones_not_screened':True,'assembly_ready':False,'best_candidates':candidates[:20],'sample_count':len(candidates)}
(out/'edge-placement-screen.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps({k:data[k] for k in ('status','sample_count')}),flush=True)
print(json.dumps(candidates[0]),flush=True);os._exit(0)
