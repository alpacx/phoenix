#!/usr/bin/env python3
"""Local CPU converter bypass geometry; loop impedance and stability unqualified."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/startup-power/pcb'
src=D/'cpu-switch.kicad_pcb';proof=json.loads((D/'cpu-switch.json').read_text());assert proof['status']=='CPU_SWITCH_INPUT_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
for ref,xy,angle in [('C1013',(65.5,15.5),0),('L402',(53,14),0),('C1002',(67,22),270)]:
 f=fs[ref];assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads()),ref
 f.SetPosition(vec(xy));f.SetOrientationDegrees(angle)
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def route(net,width,points):
 for a,z in zip(points,points[1:]):
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(p.F_Cu);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
route('VDD_CPU',.8,[(61,14.97),(64.02,14.97),(64.55,15.5)])
route('GND',.4,[(66.45,15.5),(66.45,14.35),(66.8,14)])
route('+5V_MAIN',.4,[(62.55,22),(62.55,21.65),(63.4,20.8),(66.75,20.8),(67,21.05)])
route('GND',.3,[(67,22.95),(66.35,22.95),(65.4,22),(65.3,22)])
route('GND',.3,[(64.45,22),(65.3,22)]);via('GND',(65.3,22))
# Seven RK860 ground balls; keep 0.2 mm necks inside the 0.4 mm pitch array.
route('GND',.2,[(59.4,22),(60.6,22)])
route('GND',.2,[(59.4,22.4),(60.2,22.4)])
for x in [59.4,59.8,60.2]:route('GND',.2,[(x,22),(x,22.4)])
route('GND',.2,[(59.4,22),(58.8,22)])
route('GND',.3,[(58.8,22),(58.6,22.2),(58.6,24),(58.8,24.2)])
out=D/'cpu-caps.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'cpu-caps-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'cpu-switch-drc.json').read_text()),json.loads((D/'cpu-caps-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('L1001','2'),('C1013','1')),(('C1001','1'),('C1002','1'))]+[((r,'2'),('C435','2')) for r in ['C1001','C1002','C1013']]+[(('U10',n),('C435','2')) for n in ['B2','B3','B4','C1','C2','C3','C4']]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'CPU_BYPASSES_CONNECTED' if accepted else 'REJECTED_CPU_BYPASSES','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'electrical_qualified':False,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'cpu-caps.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
