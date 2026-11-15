#!/usr/bin/env python3
"""CPU switch/input draft. Widths and via topology require power qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/startup-power/pcb'
src=D/'cpu-feedback.kicad_pcb';proof=json.loads((D/'cpu-feedback.json').read_text());assert proof['status']=='CPU_FEEDBACK_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()}
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points):
 for a,z in zip(points,points[1:]):
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(p.F_Cu);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
route('CPU_BUCK_EN',.2,[(60.2,22.8),(60.2,23.6),(60.71,24.11),(60.71,24.4)])
out=D/'cpu-enable.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'cpu-enable-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'cpu-feedback-drc.json').read_text()),json.loads((D/'cpu-enable-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('U10','A2'),('R1002','2'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'CPU_ENABLE_LOCAL_CONNECTED' if accepted else 'REJECTED_CPU_ENABLE','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'electrical_qualified':False,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'cpu-enable.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
