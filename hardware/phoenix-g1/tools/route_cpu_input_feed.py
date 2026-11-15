#!/usr/bin/env python3
"""System buck local power copper, explicitly not current/thermal qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'vdc-passives.kicad_pcb';proof=json.loads((D/'vdc-passives.json').read_text());assert proof['status']=='VDC_PASSIVES_CONNECTED_PIN61_OPEN';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
via('+5V_MAIN',(64.5,20.5))
route('+5V_MAIN',.4,[(64.5,20.5),(64.5,20.8)])
route('+5V_MAIN',.8,[(52.6,31.55),(54,32.95),(60.5,32.95),(60.5,24.5),(64.5,20.5)],p.In2_Cu)
out=D/'cpu-input-feed.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'cpu-input-feed-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'vdc-passives-drc.json').read_text()),json.loads((D/'cpu-input-feed-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('C1001','1'),('C1203','1'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'CPU_INPUT_FEED_CONNECTED' if accepted else 'REJECTED_CPU_INPUT_FEED','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'cpu-input-feed.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
