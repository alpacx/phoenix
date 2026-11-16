#!/usr/bin/env python3
"""Place and connect the existing display I/O rail bleed resistor. Geometry/continuity only."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'display-reservoir.kicad_pcb';proof=json.loads((D/'display-reservoir.json').read_text());assert proof['status']=='DISPLAY_RESERVOIR_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
b.BuildConnectivity()
f=next(f for f in b.GetFootprints() if f.GetReference()=='R1804')
assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads())
if f.GetLayer()!=p.F_Cu:f.Flip(f.GetPosition(),False)
f.SetOrientationDegrees(270)
from local_pcb_router import LocalRouter
import math
r=LocalRouter(b,(27,26,37,39),width=.2,grid=.05)
r.pads=[q for q in r.pads if q.GetParentFootprint().GetReference()!='R1804']
blocks={q.GetNumber():r.blocked(p.F_Cu,q.GetNetname(),math.hypot(p.ToMM(q.GetSize().x),p.ToMM(q.GetSize().y))) for q in f.Pads()}
obstacles=[g.GetCourtyard(p.F_Cu).BBox() for g in b.GetFootprints() if g.GetReference()!='R1804' and g.GetLayer()==p.F_Cu]
candidates=[(x/4,y/4) for x in range(110,145) for y in range(108,150)]
candidates.sort(key=lambda xy:math.dist(xy,(30,31.51)))
held=[];found=False
for xy in candidates:
 f.SetPosition(vec(xy));box=f.GetCourtyard(p.F_Cu).BBox()
 if any(box.Intersects(other) for other in obstacles):continue
 if any(r.cell(r.xy(q)) in blocks[q.GetNumber()] for q in f.Pads()):continue
 rr=LocalRouter(b,(27,26,37,39),width=.2,grid=.025);rr.max_expansions=200000
 a=pads['R1804','1'];z=pads['R1815','2']
 path=rr.solve(rr.blocked(p.F_Cu,'+3V3_IO'),rr.cell(rr.xy(a)),rr.cell(rr.xy(z)))
 if not path:continue
 before={t.m_Uuid.AsString() for t in b.GetTracks()}
 route('+3V3_IO',.2,[rr.xy(a)]+path+[rr.xy(z)])
 gr=LocalRouter(b,(27,26,37,39),width=.2,grid=.05)
 tree=gr.paths_from(gr.blocked(p.F_Cu,'GND'),gr.cell(gr.xy(pads['R1804','2'])),6)
 forbidden=set()
 for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= gr.blocked(layer,'GND',.45,True)
 choices=sorted((q for q in tree['distances'] if q not in forbidden),key=tree['distances'].get)
 if not choices:
  for t in list(b.GetTracks()):
   if t.m_Uuid.AsString() not in before:b.Remove(t);held.append(t)
  continue
 q=choices[0];route('GND',.2,[gr.xy(pads['R1804','2'])]+gr.path_from_tree(tree,q));via('GND',gr.world(q));found=True;break
assert found
print('R1804 position',xy,flush=True)
out=D/'display-io-bleed.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'display-io-bleed-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'display-reservoir-drc.json').read_text()),json.loads((D/'display-io-bleed-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('R1804','1'),('U20','3')),(('R1804','2'),('U20','2'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'DISPLAY_IO_BLEED_CONNECTED' if accepted else 'REJECTED_DISPLAY_IO_BLEED','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'display-io-bleed.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
