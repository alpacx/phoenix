#!/usr/bin/env python3
"""System buck local power copper, explicitly not current/thermal qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';S=E/'system-3v3';D=E/'pmic-ldo-inputs/pcb';D.mkdir(parents=True,exist_ok=True)
proof=json.loads((D/'rtc-link.json').read_text());src=D/'rtc-link.kicad_pcb';assert proof['status']=='PMIC_RTC_GROUP_JOINED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
replaced=[]
for t in list(b.GetTracks()):
 if t.GetNetname()=='GND':
  if isinstance(t,p.PCB_VIA) and t.GetPosition()==vec((57.8,4.75)):
   replaced.append(t.m_Uuid.AsString());t.SetPosition(vec((58.4,4.8)))
  elif not isinstance(t,p.PCB_VIA) and t.GetEnd()==vec((57.8,4.75)):
   replaced.append(t.m_Uuid.AsString());t.SetEnd(vec((58.4,4.8)))
 elif t.GetNetname()=='+3V3_SYS' and t.GetLayer()==p.B_Cu and not isinstance(t,p.PCB_VIA):
  if t.GetStart()==vec((58.5,3.2)) and t.GetEnd()==vec((58.5,4.8)):
   replaced.append(t.m_Uuid.AsString());t.SetStart(vec((58.8,3.2)));t.SetEnd(vec((58.8,4.3)))
  elif t.GetStart()==vec((58.5,4.8)):
   replaced.append(t.m_Uuid.AsString());t.SetStart(vec((59.1,4.8)))
assert len(replaced)==5,replaced
route('+3V3_SYS',.3,[(58.5,3.2),(58.8,3.2)],p.B_Cu)
route('+3V3_SYS',.3,[(58.8,4.3),(59.1,4.8)],p.B_Cu)
route('+3V3_SYS',.15,[(57.9,5.59),(57.9,5.0),(57.3,4.4)])
route('+3V3_SYS',.3,[(57.3,4.4),(57.3,3.2)])
out=D/'vcc4-input.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'vcc4-input-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'vcc4-input-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('U4','66'),('C484','1'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'PMIC_VCC4_INPUT_CONNECTED' if accepted else 'REJECTED_PMIC_VCC4_INPUT','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'replaced_copper':replaced,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b,replaced_copper=replaced)
(D/'vcc4-input.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
