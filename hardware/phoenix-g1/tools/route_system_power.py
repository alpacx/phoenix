#!/usr/bin/env python3
"""System buck local power copper, explicitly not current/thermal qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/system-3v3/pcb'
src=D/'placement.kicad_pcb';proof=json.loads((D/'placement.json').read_text());assert proof['status']=='SYSTEM_PLACEMENT_ACCEPTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
route('SYS_SW',.25,[(12.6,29.75),(12.6,30.25),(12.6,30.75)])
route('SYS_SW',.5,[(12.6,30.25),(11.75,30.25)])
route('SYS_SW',.8,[(11.75,30.25),(10.3,31.7),(10.3,32.65),(11.6,33.95),(14,33.95)])
route('+5V_MAIN',.25,[(15.4,29.75),(15.4,30.25),(15.4,30.75)])
route('+5V_MAIN',.5,[(15.4,30.25),(16.3,30.25),(16.3,31.3),(16.3,32.1)])
for q in [(16.3,31.3),(16.3,32.1)]:via('+5V_MAIN',q)
route('+5V_MAIN',.5,[(16.3,31.3),(16.3,32.1),(15.55,32)],p.B_Cu)
route('+5V_MAIN',.3,[(14.82,30.2),(14.82,30.7),(15.42,31.3),(16.3,31.3)],p.B_Cu)
# Ground pin necks stay within the QFN's pitch; thermal vias need process review.
for x,y in [(13.25,13.5),(13.75,13.75),(14.25,14.25),(14.75,14.5)]:route('GND',.25,[(x,31.9),(y,31.55),(y,31.2)])
for x,y in [(13.25,13.5),(13.75,13.75)]:route('GND',.25,[(x,29.1),(y,29.45),(y,29.8)])
for q in [(13.8,30.5),(13.8,31.25),(17.4,33.3)]:via('GND',q)
route('GND',.4,[(17.45,32),(17.45,33.25),(17.4,33.3)],p.B_Cu)
route('GND',.2,[(15.78,30.2),(15.78,29.8),(15.4,29.42),(14,29.42),(13.8,29.62),(13.8,30.5)],p.B_Cu)
route('+3V3_SYS',1.0,[(14,38.05),(17.85,38.05),(18.55,38.75)])
route('+3V3_SYS',.8,[(18.55,38.75),(18.55,36.5)])
route('GND',.4,[(20.45,36.5),(21.2,37.0),(21.2,38.75),(20.45,38.75)])
via('GND',(21.2,38.75))
out=D/'local-power.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'local-power-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'placement-drc.json').read_text()),json.loads((D/'local-power-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('U17',n),('L1301','1')) for n in ['1','2','3']]+[(('U17',n),('C1301','1')) for n in ['10','11','12']]+[(('C1301','1'),('C1302','1'))]+[(('U17',n),('C435','2')) for n in ['5','6','7','8','15','16','17']]+[((r,'2'),('C435','2')) for r in ['C1301','C1302','C1304','C1305']]+[(('L1301','2'),(r,'1')) for r in ['C1304','C1305']]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'SYSTEM_LOCAL_POWER_CONNECTED' if accepted else 'REJECTED_SYSTEM_POWER','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'local-power.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
