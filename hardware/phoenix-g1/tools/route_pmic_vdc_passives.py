#!/usr/bin/env python3
"""System buck local power copper, explicitly not current/thermal qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';S=E/'system-3v3';D=E/'pmic-ldo-inputs/pcb';D.mkdir(parents=True,exist_ok=True)
proof=json.loads((D/'vdc-divider-input.json').read_text());src=D/'vdc-divider-input.kicad_pcb';assert proof['status']=='VDC_DIVIDER_INPUT_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.8));v.SetDrill(p.FromMM(.4));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
b.BuildConnectivity()
for ref,xy in [('R411',(58.5,7.3)),('C410',(57.6,9.2))]:
 f=next(f for f in b.GetFootprints() if f.GetReference()==ref)
 assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads())
 f.Flip(f.GetPosition(),False);f.SetPosition(vec(xy));f.SetOrientationDegrees(0)
route('PMIC_VDC',.2,[(57.49,6),(57.49,6.8),(57.99,7.3),(57.72,7.57),(57.72,8.5),(57.12,9.1),(57.12,9.2)],p.B_Cu)
route('GND',.3,[(59.01,7.3),(59,8)],p.B_Cu)
route('GND',.3,[(58.08,9.2),(59,9)],p.B_Cu)
out=D/'vdc-passives.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'vdc-passives-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'vdc-passives-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('R410','2'),('R411','1')),(('R410','2'),('C410','1')),(('R411','2'),('C435','2')),(('C410','2'),('C435','2'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'VDC_PASSIVES_CONNECTED_PIN61_OPEN' if accepted else 'REJECTED_VDC_PASSIVES','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False,'manufacturing_requirement':'C1304/C1305 via-in-pad must be filled and capped; current capability and final stackup unqualified'}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'vdc-passives.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
