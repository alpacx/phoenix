#!/usr/bin/env python3
"""Relocate one PHY bypass with bounded routing and preservation; no PI qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'ethernet-avdd33-bypass.kicad_pcb';proof=json.loads((D/'ethernet-avdd33-bypass.json').read_text());assert proof['status']=='ETHERNET_AVDD33_BYPASS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
b.BuildConnectivity()
from local_pcb_router import LocalRouter
import math
moves={};held=[]
old=p.LoadBoard(str(D/'ethernet-clock-pins.kicad_pcb'))
oldids={v.m_Uuid.AsString() for v in old.GetTracks()}
removed=[]
for v in list(b.GetTracks()):
 x,y=p.ToMM(v.GetStart().x),p.ToMM(v.GetStart().y)
 if v.m_Uuid.AsString() not in oldids and 77.9<=x<=78.8 and abs(y-34.5)<.01:
  removed.append(v.m_Uuid.AsString());b.Remove(v);held.append(v)
assert len(removed)==3,removed
b.BuildConnectivity()
for pin,ref in [('3','C512')]:
 f=next(f for f in b.GetFootprints() if f.GetReference()==ref)
 assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads()),ref
 if f.GetLayer()!=p.F_Cu:f.Flip(f.GetPosition(),False)
 f.SetOrientationDegrees(270)
 a=pads['U5',pin];z=pads[ref,'1']
 r=LocalRouter(b,(59,31,69,39),width=.2,grid=.05)
 r.pads=[q for q in r.pads if q.GetParentFootprint().GetReference()!=ref]
 blocked={q.GetNumber():r.blocked(p.F_Cu,q.GetNetname(),math.hypot(p.ToMM(q.GetSize().x),p.ToMM(q.GetSize().y))) for q in f.Pads()}
 obstacles=[g.GetCourtyard(p.F_Cu).BBox() for g in b.GetFootprints() if g.GetReference()!=ref and g.GetLayer()==p.F_Cu]
 candidates=[(x/4,y/4) for x in range(236,277) for y in range(124,153)]
 candidates.sort(key=lambda xy:math.dist(xy,r.xy(a)))
 found=False;counts=dict(outside=0,courtyard=0,pad_copper=0,no_signal_path=0,path_too_long=0,no_ground=0)
 for xy,angle in [(xy,angle) for xy in candidates for angle in [0,90,180,270]]:
  f.SetOrientationDegrees(angle)
  if math.dist(xy,r.xy(a))>4:counts["outside"]+=1;continue
  f.SetPosition(vec(xy));box=f.GetCourtyard(p.F_Cu).BBox()
  if any(box.Intersects(other) for other in obstacles):counts["courtyard"]+=1;continue
  if any(r.cell(r.xy(q)) in blocked[q.GetNumber()] for q in f.Pads()):counts["pad_copper"]+=1;continue
  rr=LocalRouter(b,(59,31,69,39),width=.2,grid=.025);rr.max_expansions=150000
  path=rr.solve(rr.blocked(p.F_Cu,a.GetNetname()),rr.cell(rr.xy(a)),rr.cell(rr.xy(z)))
  if not path:counts["no_signal_path"]+=1;continue
  if sum(math.dist(x,y) for x,y in zip(path,path[1:]))>4:counts["path_too_long"]+=1;continue
  before_ids={t.m_Uuid.AsString() for t in b.GetTracks()}
  route(a.GetNetname(),.2,[rr.xy(a)]+path+[rr.xy(z)])
  if True:
   gr=LocalRouter(b,(59,31,69,39),width=.2,grid=.05)
   tree=gr.paths_from(gr.blocked(p.F_Cu,'GND'),gr.cell(gr.xy(pads[ref,'2'])),3)
   forbidden=set()
   for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= gr.blocked(layer,'GND',.45,True)
   existing={gr.cell(gr.xy(v)):v for v in b.GetTracks() if isinstance(v,p.PCB_VIA) and v.GetNetname()=='GND'}
   choices=sorted((q for q in tree['distances'] if q not in forbidden or q in existing),key=tree['distances'].get)
   if not choices:
    counts["no_ground"]+=1
    for t in list(b.GetTracks()):
     if t.m_Uuid.AsString() not in before_ids:b.Remove(t);held.append(t)
    continue
   q=choices[0];route('GND',.2,[gr.xy(pads[ref,'2'])]+gr.path_from_tree(tree,q))
   if q not in existing:via('GND',gr.world(q))
  moves[ref]=xy;found=True;break
 if not found:
  report={'status':'NO_ACCEPTED_BOUNDED_BYPASS_PLACEMENT','source_sha256':proof['sha256'],'failed_ref':ref,'counts':counts,'max_signal_path_mm':4,'grid_mm':.025,'placement_pitch_mm':.25,'rotations_deg':[0,90,180,270],'board_changed':False,'note':'In-memory trial discarded. Not a proof of impossibility; review joint PHY/passive placement. No clearance or component change.'}
  (D/'ethernet-avdd10-bypass-trial.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(2)
out=D/'ethernet-avdd10-bypass.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'ethernet-avdd10-bypass-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'ethernet-avdd33-bypass-drc.json').read_text()),json.loads((D/'ethernet-avdd10-bypass-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('C512','1'),('U5','3')),(('C512','2'),('U20','2'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
from audit_mount_component_reservations import screen
key=lambda row:(row['reservation'],row['ref'])
old_conflicts={key(row) for row in screen(p.LoadBoard(str(src)))}
new_conflicts=sorted({key(row) for row in screen(b)}-old_conflicts)
accepted=not new and not new_conflicts and all(c['connected'] for c in checks)
r={'status':'ETHERNET_AVDD10_BYPASS_CONNECTED' if accepted else 'REJECTED_ETHERNET_AVDD10_BYPASS','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'introduced_mechanical_conflicts':new_conflicts,'assembly_ready':False,'moved_refs_mm':moves,'replaced_copper':removed,'limitations':['Only C512 bypass for U5.3 relocated. Supply sources and other bypass branches remain incomplete.','Continuity and geometry are not PI, regulator stability or manufacturing qualification.']}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b,replaced_copper=removed)
(D/'ethernet-avdd10-bypass.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
