#!/usr/bin/env python3
"""Necessary, not sufficient, courtyard enclosure check against physical pads."""
from pathlib import Path
import hashlib,json,sys
import pcbnew as p
R=Path(__file__).resolve().parents[1]/'migration-rk3562';path=R/'kicad/pcb/phoenix-g1.kicad_pcb';b=p.LoadBoard(str(path))
def bounds(a):
 q=a.GetBoundingBox();return [p.ToMM(x) for x in [q.GetX(),q.GetY(),q.GetRight(),q.GetBottom()]]
findings=[]
for f in b.GetFootprints():
 layer=p.F_CrtYd if f.GetLayer()==p.F_Cu else p.B_CrtYd
 shapes=[bounds(a) for a in f.GraphicalItems() if a.GetLayer()==layer]
 if not shapes:
  findings.append({'ref':f.GetReference(),'issue':'No courtyard graphics on component side'});continue
 envelope=[min(q[0] for q in shapes),min(q[1] for q in shapes),max(q[2] for q in shapes),max(q[3] for q in shapes)]
 outside=[]
 for pad in f.Pads():
  if not pad.IsOnLayer(f.GetLayer()):continue
  q=bounds(pad)
  if q[0]<envelope[0]-.001 or q[1]<envelope[1]-.001 or q[2]>envelope[2]+.001 or q[3]>envelope[3]+.001:
   outside.append({'pin':pad.GetNumber(),'pad_bounds_mm':q})
 if outside:findings.append({'ref':f.GetReference(),'issue':'Pad extends beyond even the courtyard bounding envelope','courtyard_envelope_mm':envelope,'pads_outside':outside})
report={'status':'FOOTPRINT ASSEMBLY ENVELOPES REQUIRE REVIEW' if findings else 'BOUNDING ENVELOPE SCREEN PASSED; CLEARANCES STILL UNQUALIFIED','pcb_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source':'https://klc.kicad.org/footprint/f5/f5.3/','footprints_checked':len(list(b.GetFootprints())),'findings':sorted(findings,key=lambda a:a['ref']),'limitations':['Bounding-box containment is a necessary condition only: concave polygon containment and closure are not tested.','No clearance margin is credited by this check; KLC nominal body/land offsets and connector mating envelopes still require validation.','Does not alter pad geometry, courtyards or placements. Passing PCB DRC cannot establish correctness of imported courtyard geometry.'],'production_ready':False}
(R/'review/courtyard-envelope-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'checked':report['footprints_checked'],'flagged_refs':[a['ref'] for a in report['findings']]},indent=2))

if '--require-enclosure' in sys.argv:
 assert not findings, 'Pad/courtyard enclosure regression'
