#!/usr/bin/env python3
"""System buck local power copper, explicitly not current/thermal qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'cpu-input-feed.kicad_pcb';proof=json.loads((D/'cpu-input-feed.json').read_text());assert proof['status']=='CPU_INPUT_FEED_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
via('+5V_MAIN',(45.6,32.5))
route('+5V_MAIN',.3,[(45,34),(45.6,33.4),(45.6,32.5)],p.B_Cu)
route('+5V_MAIN',.3,[(45.6,32.5),(45.6,35.3)],p.In3_Cu)
out=D/'five-volt-testpoint.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'five-volt-testpoint-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'cpu-input-feed-drc.json').read_text()),json.loads((D/'five-volt-testpoint-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('TP3','1'),('C1203','1'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'FIVE_VOLT_TESTPOINT_CONNECTED' if accepted else 'REJECTED_FIVE_VOLT_TESTPOINT','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'five-volt-testpoint.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
