#!/usr/bin/env python3
"""Bounded same-side relocation study; never qualifies regulator placement."""
import pcbnew as p,json,math,shutil,subprocess,collections,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'migration-rk3562/experiments/stacked-expansion';D=O/'mechanical';cp=json.loads((O/'working-candidate.json').read_text());source=O/cp['board'];assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(source));b.BuildConnectivity();conn=b.GetConnectivity();spec=json.loads((D/'mounting-interface.json').read_text());sites=[m['center_mm'] for m in spec['mounts']];fps={f.GetReference():f for f in b.GetFootprints()}
def bb(a):
 z=a.GetBoundingBox();return [p.ToMM(v) for v in (z.GetX(),z.GetY(),z.GetRight(),z.GetBottom())]
def shapes(f):return [bb(a) for a in list(f.Pads())+[g for g in f.GraphicalItems() if g.GetLayer() in (p.F_CrtYd,p.B_CrtYd)]]
def near(z,x,y):return math.hypot(max(z[0]-x,0,x-z[2]),max(z[1]-y,0,y-z[3]))<2.7
out=D/'mount-local-trial.kicad_pcb';records=[]
for ref in ['C422','C425','R1811','C445','C470','L405','R431']:
 f=fps[ref];assert not any(conn.GetConnectedTracks(a) for a in f.Pads());old=f.GetPosition();xy=(p.ToMM(old.x),p.ToMM(old.y));obstacles=[]
 for other in b.GetFootprints():
  if other==f:continue
  if other.GetLayer()==f.GetLayer() or any(a.GetAttribute()==p.PAD_ATTRIB_PTH for a in other.Pads()):obstacles+=shapes(other)
 obstacles += [bb(t) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) or t.GetLayer()==f.GetLayer()]
 found=False
 for dx,dy in sorted([(x/4,y/4) for x in range(-16,17) for y in range(-16,17) if x*x+y*y<=256],key=lambda q:math.hypot(*q)):
  x,y=xy[0]+dx,xy[1]+dy;f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));zs=shapes(f)
  if any(z[0]<.5 or z[1]<.5 or z[2]>89.5 or z[3]>39.5 for z in zs):continue
  if any(near(z,sx,sy) for z in zs for sx,sy in sites):continue
  if any(not(z[2]+.25<q[0] or q[2]+.25<z[0] or z[3]+.25<q[1] or q[3]+.25<z[1]) for z in zs for q in obstacles):continue
  found=True;break
 if not found:f.SetPosition(old)
 records.append({'ref':ref,'from_mm':xy,'to_mm':[p.ToMM(f.GetPosition().x),p.ToMM(f.GetPosition().y)],'cleared':found,'electrical_placement_qualified':False})
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(source.with_suffix('.'+ext),out.with_suffix('.'+ext))
cli='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli';subprocess.run([cli,'pcb','drc','--format','json','-o',str(D/'mount-local-trial-drc.json'),str(out)],check=True,capture_output=True)
counts=lambda path:collections.Counter(v['type'] for v in json.loads(path.read_text())['violations']);base=counts(O/'pcb/aux-io-drc.json');now=counts(D/'mount-local-trial-drc.json')
report={'status':'LOCAL_RELOCATION_STUDY_NOT_PROMOTED','source_sha256':cp['sha256'],'moves':records,'new_DRC_counts':dict(now-base),'maximum_search_displacement_mm':4,'side_unchanged':True,'actual_holes_created':False,'assembly_ready':False};(D/'mount-local-trial.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
