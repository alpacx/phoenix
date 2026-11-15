#!/usr/bin/env python3
"""Kelvin feedback from output capacitor; RC values and loop stability unqualified."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
from local_pcb_router import LocalRouter
import math
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/startup-power/pcb'
src=D/'cpu-output-bank.kicad_pcb';proof=json.loads((D/'cpu-output-bank.json').read_text());assert proof['status']=='CPU_OUTPUT_BANK_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
for ref,xy in [('R1001',(57.4,25.2)),('C1020',(57.4,26.4)),('R1002',(60.2,24.4))]:
 f=fs[ref];assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads()),ref
 f.SetPosition(vec(xy));f.SetOrientationDegrees(0)
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
# Remove only the four newly created local ground escape segments, not ground-ball ties.
remove_paths=[((59.4,22),(58.8,22)),((58.8,22),(58.6,22.2)),((58.6,22.2),(58.6,24)),((58.6,24),(58.8,24.2))]
held=[];replaced=[]
for a,z in remove_paths:
 matches=[t for t in b.GetTracks() if not isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND' and t.GetLayer()==p.F_Cu and t.GetStart()==vec(a) and t.GetEnd()==vec(z)]
 assert len(matches)==1,(a,z)
 t=matches[0];replaced.append(t.m_Uuid.AsString());b.Remove(t);held.append(t)
route('GND',.2,[(60.6,22),(61.2,22)])
route('GND',.3,[(61.2,22),(61.7,22.5),(61.7,23.3),(64.45,23.3),(65.3,22.45),(65.3,22)])
route('CPU_FB_SENSE',.2,[(59.4,22.8),(58.45,22.8),(58.5,23),(58.5,23.6),(58.1,24),(57.91,25.2),(57.88,26.4)])
route('VDD_CPU',.2,[(56.89,25.2),(56.92,26.4)])
route('VDD_CPU',.2,[(64.55,18),(63.9,18.5)])
via('VDD_CPU',(63.9,18.5))
# This is the low-current Kelvin branch, never the CPU load-current route.
router=LocalRouter(b,(54,18,66,30),width=.2,clearance=.2,grid=.1)
forbidden=set()
for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:
 forbidden |= router.blocked(layer,'VDD_CPU',.45,True)
front=router.blocked(p.F_Cu,'VDD_CPU');inner=router.blocked(p.In1_Cu,'VDD_CPU')
start=router.cell((56.92,26.4));tree=router.paths_from(front,start,3.5)
found=None
for cell in sorted(tree['distances'],key=tree['distances'].get):
 if cell in forbidden:continue
 inner_path=router.solve(inner,router.cell((63.9,18.5)),cell)
 if not inner_path:continue
 front_path=[(56.92,26.4)]+router.path_from_tree(tree,cell)
 via_xy=router.world(cell);found=(via_xy,front_path,inner_path);break
assert found,'No local Kelvin escape via'
via_xy,front_path,inner_path=found
route('VDD_CPU',.2,front_path);via('VDD_CPU',via_xy);route('VDD_CPU',.2,inner_path,p.In1_Cu)

out=D/'cpu-feedback.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'cpu-feedback-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'cpu-output-bank-drc.json').read_text()),json.loads((D/'cpu-feedback-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('U10','A4'),('R1001','2')),(('U10','A4'),('C1020','2')),(('C1012','1'),('R1001','1')),(('C1012','1'),('C1020','1'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'CPU_FEEDBACK_CONNECTED' if accepted else 'REJECTED_CPU_FEEDBACK','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'kelvin_escape_via_mm':via_xy,'kelvin_inner_length_mm':sum(math.dist(a,z) for a,z in zip(inner_path,inner_path[1:])),'replaced_copper':replaced,'new_violations':new,'electrical_qualified':False,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b,replaced_copper=replaced)
(D/'cpu-feedback.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
