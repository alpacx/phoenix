#!/usr/bin/env python3
"""Local CPU converter bypass geometry; loop impedance and stability unqualified."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/startup-power/pcb'
src=D/'cpu-caps.kicad_pcb';proof=json.loads((D/'cpu-caps.json').read_text());assert proof['status']=='CPU_BYPASSES_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
for ref,xy,flip in [('C1012',(65.5,18),False),('C1011',(65.5,11.5),True),('L403',(66.5,9.5),False)]:
 f=fs[ref];assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads()),ref
 if flip:f.Flip(f.GetPosition(),False)
 f.SetPosition(vec(xy));f.SetOrientationDegrees(0)
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
route('VDD_CPU',.6,[(64.55,15.5),(64.55,18)])
route('GND',.4,[(66.45,18),(66.45,15.5)])
route('VDD_CPU',.5,[(64.55,15.5),(64.3,15.25),(64.3,14.1),(63.45,14.1),(63.45,12.8),(64.3,12.25)])
via('VDD_CPU',(64.3,12.25))
route('VDD_CPU',.5,[(64.3,12.25),(64.55,12.0),(64.55,11.5)],p.B_Cu)
route('GND',.4,[(66.45,11.5),(66.8,11.85),(66.8,14)],p.B_Cu)
out=D/'cpu-output-bank.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'cpu-output-bank-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'cpu-caps-drc.json').read_text()),json.loads((D/'cpu-output-bank-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('L1001','2'),(r,'1')) for r in ['C1011','C1012','C1013']]+[((r,'2'),('C435','2')) for r in ['C1011','C1012','C1013']]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'CPU_OUTPUT_BANK_CONNECTED' if accepted else 'REJECTED_CPU_OUTPUT_BANK','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'electrical_qualified':False,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'cpu-output-bank.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
