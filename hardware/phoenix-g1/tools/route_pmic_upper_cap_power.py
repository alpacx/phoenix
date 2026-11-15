#!/usr/bin/env python3
"""System buck local power copper, explicitly not current/thermal qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';S=E/'system-3v3';D=E/'pmic-ldo-inputs/pcb';D.mkdir(parents=True,exist_ok=True)
proof=json.loads((D/'upper-cap-grounds.json').read_text());src=D/'upper-cap-grounds.kicad_pcb';assert proof['status']=='PMIC_UPPER_CAP_GROUNDS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
route('+3V3_SYS',.3,[(55.65,6.6),(55.65,5.2),(57.3,3.55),(57.3,3.2)],p.In4_Cu)
via('+3V3_SYS',(57.3,3.2))
route('+3V3_SYS',.3,[(57.3,3.2),(58.5,3.2),(58.5,4.8),(60.48,4.8),(60.48,4)],p.B_Cu)
route('+3V3_SYS',.3,[(58.5,3.2),(57.98,4)],p.B_Cu)
out=D/'upper-cap-power.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'upper-cap-power-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'upper-cap-power-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('C481','1'),('C480','1')),(('C484','1'),('C480','1'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'PMIC_UPPER_CAP_POWER_CONNECTED' if accepted else 'REJECTED_PMIC_UPPER_CAP_POWER','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'upper-cap-power.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
