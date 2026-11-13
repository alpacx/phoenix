#!/usr/bin/env python3
"""Independent mechanical candidate: clear daughterboard M2 attachment sites."""
import pcbnew as p,json,math,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'migration-rk3562/experiments/stacked-expansion';D=O/'mechanical';b=p.LoadBoard(str(O/'pcb/candidate.kicad_pcb'));b.BuildConnectivity();conn=b.GetConnectivity()
spec=json.loads((D/'mounting-interface.json').read_text());sites=[m['center_mm'] for m in spec['mounts']];refs=[r for m in spec['mounts'] for r in m['blocking_components']];fps={f.GetReference():f for f in b.GetFootprints()}
def bb(a):
 z=a.GetBoundingBox();return [p.ToMM(v) for v in (z.GetX(),z.GetY(),z.GetRight(),z.GetBottom())]
def shapes(f):return [bb(a) for a in list(f.Pads())+[g for g in f.GraphicalItems() if g.GetLayer() in (p.F_CrtYd,p.B_CrtYd)]]
def near(z,x,y):return math.hypot(max(z[0]-x,0,x-z[2]),max(z[1]-y,0,y-z[3]))<2.7
moved=[]
for ref in refs:
 f=fps[ref];assert not any(conn.GetConnectedTracks(a) for a in f.Pads()),ref
 old=f.GetPosition();oldxy=[p.ToMM(old.x),p.ToMM(old.y)];originalflip=f.IsFlipped()
 obstacles=[]
 for other in b.GetFootprints():
  if other==f:continue
  # Conservative all-side screening avoids creating inaccessible underside parts.
  obstacles+=shapes(other)
 obstacles += [bb(t) for t in b.GetTracks()]
 candidates=sorted([(math.hypot(x/2-oldxy[0],y/2-oldxy[1]),x/2,y/2) for x in range(3,177) for y in range(3,77)])
 found=False
 for _,x,y in candidates:
  f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));zs=shapes(f)
  if any(z[0]<.5 or z[1]<.5 or z[2]>89.5 or z[3]>39.5 for z in zs):continue
  if any(near(z,sx,sy) for z in zs for sx,sy in sites):continue
  if any(not (z[2]+.25<q[0] or q[2]+.25<z[0] or z[3]+.25<q[1] or q[3]+.25<z[1]) for z in zs for q in obstacles):continue
  found=True;break
 if not found:f.SetPosition(old)
 moved.append({'ref':ref,'from_mm':oldxy,'to_mm':[p.ToMM(f.GetPosition().x),p.ToMM(f.GetPosition().y)],'cleared':found,'electrical_placement_qualified':False})
# Save trial regardless; never promote on placement alone.
p.ZONE_FILLER(b).Fill(b.Zones());dest=D/'mount-clearance-trial.kicad_pcb';p.SaveBoard(str(dest),b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(O/f'pcb/candidate.{ext}',dest.with_suffix('.'+ext))
(D/'fp-lib-table').write_text((O/'pcb/fp-lib-table').read_text())
report={'status':'PLACEMENT_TRIAL_NOT_RELEASE','moves':moved,'actual_holes_created':False,'assembly_ready':False}
(D/'mount-clearance-trial.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
