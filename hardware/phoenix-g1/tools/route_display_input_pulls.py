#!/usr/bin/env python3
"""Place and connect display input bias resistors; replace only the prior buffer feed. Geometry/continuity only."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'display-buffer-feed.kicad_pcb';proof=json.loads((D/'display-buffer-feed.json').read_text());assert proof['status']=='DISPLAY_BUFFER_FEED_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
b.BuildConnectivity()
old_bypass=p.LoadBoard(str(D/'display-buffer-bypass.kicad_pcb'))
old_feed=p.LoadBoard(str(D/'display-buffer-feed.kicad_pcb'))
prior={t.m_Uuid.AsString() for t in old_bypass.GetTracks()}
replaced={t.m_Uuid.AsString() for t in old_feed.GetTracks() if t.m_Uuid.AsString() not in prior}
held=[]
for t in list(b.GetTracks()):
 if t.m_Uuid.AsString() in replaced:b.Remove(t);held.append(t)
from local_pcb_router import LocalRouter
import math
moves={}
for pin,ref in [('2','R1811'),('3','R1812'),('4','R1813'),('5','R1814'),('6','R1815')]:
 f=next(f for f in b.GetFootprints() if f.GetReference()==ref)
 assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads()),ref
 if f.GetLayer()!=p.F_Cu:f.Flip(f.GetPosition(),False)
 f.SetOrientationDegrees(270)
 a=pads['U21',pin];z=pads[ref,'1']
 r=LocalRouter(b,(18,27,34,39),width=.2,grid=.05)
 r.pads=[q for q in r.pads if q.GetParentFootprint().GetReference()!=ref]
 blocked={q.GetNumber():r.blocked(p.F_Cu,q.GetNetname(),math.hypot(p.ToMM(q.GetSize().x),p.ToMM(q.GetSize().y))) for q in f.Pads()}
 obstacles=[g.GetCourtyard(p.F_Cu).BBox() for g in b.GetFootprints() if g.GetReference()!=ref and g.GetLayer()==p.F_Cu]
 candidates=[(x/4,y/4) for x in range(76,133) for y in range(117,151)]
 candidates.sort(key=lambda xy:math.dist(xy,r.xy(a)))
 found=False
 for xy in candidates:
  f.SetPosition(vec(xy));box=f.GetCourtyard(p.F_Cu).BBox()
  if any(box.Intersects(other) for other in obstacles):continue
  if any(r.cell(r.xy(q)) in blocked[q.GetNumber()] for q in f.Pads()):continue
  rr=LocalRouter(b,(18,27,34,39),width=.2,grid=.025);rr.max_expansions=150000
  path=rr.solve(rr.blocked(p.F_Cu,a.GetNetname()),rr.cell(rr.xy(a)),rr.cell(rr.xy(z)))
  if not path:continue
  before_ids={t.m_Uuid.AsString() for t in b.GetTracks()}
  route(a.GetNetname(),.2,[rr.xy(a)]+path+[rr.xy(z)])
  if ref!='R1815':
   gr=LocalRouter(b,(18,27,34,39),width=.2,grid=.05)
   tree=gr.paths_from(gr.blocked(p.F_Cu,'GND'),gr.cell(gr.xy(pads[ref,'2'])),8)
   forbidden=set()
   for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= gr.blocked(layer,'GND',.45,True)
   existing={gr.cell(gr.xy(v)):v for v in b.GetTracks() if isinstance(v,p.PCB_VIA) and v.GetNetname()=='GND'}
   choices=sorted((q for q in tree['distances'] if q not in forbidden or q in existing),key=tree['distances'].get)
   if not choices:
    for t in list(b.GetTracks()):
     if t.m_Uuid.AsString() not in before_ids:b.Remove(t);held.append(t)
    continue
   q=choices[0];route('GND',.2,[gr.xy(pads[ref,'2'])]+gr.path_from_tree(tree,q))
   if q not in existing:via('GND',gr.world(q))
  moves[ref]=xy;found=True;break
 assert found,ref
print('placement',moves,flush=True)
from local_pcb_router import LocalRouter
r=LocalRouter(b,(19,20,30,37),width=.3,grid=.025);r.max_expansions=200000
start=r.xy(pads['C1811','1']);goal=r.xy(pads['C1802','1'])
path=r.solve(r.blocked(p.F_Cu,'+3V0_LCD'),r.cell(start),r.cell(goal))
if path:
 route('+3V0_LCD',.3,[start]+path+[goal])
else:
 forbidden=set()
 for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= r.blocked(layer,'+3V0_LCD',.45,True)
 blocked=r.blocked(p.F_Cu,'+3V0_LCD')
 trees=[r.paths_from(blocked,r.cell(point),8) for point in [start,goal]]
 options=[]
 for tree in trees:
  candidates=sorted((q for q in tree['distances'] if q not in forbidden),key=tree['distances'].get)
  chosen=[]
  for q in candidates:
   if all(math.dist(r.world(q),r.world(z))>.5 for z in chosen):chosen.append(q)
   if len(chosen)==12:break
  options.append(chosen)
 inner=r.blocked(p.In2_Cu,'+3V0_LCD');connected=False
 for a in options[0]:
  for z in options[1]:
   path=r.solve(inner,a,z)
   if not path:continue
   route('+3V0_LCD',.3,[start]+r.path_from_tree(trees[0],a))
   route('+3V0_LCD',.3,[goal]+r.path_from_tree(trees[1],z))
   via('+3V0_LCD',r.world(a));via('+3V0_LCD',r.world(z))
   route('+3V0_LCD',.3,path,p.In2_Cu);connected=True;break
  if connected:break
 assert connected,'No feed after input placement'

out=D/'display-input-pulls.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'display-input-pulls-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'display-buffer-feed-drc.json').read_text()),json.loads((D/'display-input-pulls-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('U21',pin),(ref,'1')) for pin,ref in [('2','R1811'),('3','R1812'),('4','R1813'),('5','R1814'),('6','R1815')]]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
checks.extend({'from':ref+'.2','to':'U20.2','connected':pads['U20','2'].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[ref,'2'])}} for ref in ['R1811','R1812','R1813','R1814'])
accepted=not new and all(c['connected'] for c in checks)
r={'moved_positions_mm':moves,'status':'DISPLAY_INPUT_PULLS_CONNECTED' if accepted else 'REJECTED_DISPLAY_INPUT_PULLS','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b,replaced_copper=replaced)
(D/'display-input-pulls.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
