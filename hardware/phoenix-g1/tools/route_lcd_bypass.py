#!/usr/bin/env python3
"""LCD LDO local bypass draft; not stability, current or thermal qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/aux-mount-clear/pcb'
src=D/'h8103-hole.kicad_pcb';proof=json.loads((D/'h8103-hole.json').read_text());assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
out=D/'lcd-bypass.kicad_pcb';b=p.LoadBoard(str(src));fs={f.GetReference():f for f in b.GetFootprints()};fs['C1802'].SetOrientationDegrees(180)
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
for ref in ['C1802','U20']:
 pad=pads[ref,'2'];assert pad.GetNetname()=='GND'
 v=p.PCB_VIA(b);v.SetPosition(vec((24.02,32.8)) if ref=='C1802' else vec((28.95,32)));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(pad.GetNetCode());b.Add(v)
for ref,path in [('C1801',[(28.2,32.95),(28.2,33.68),(28.77,34.25)]),('C1802',[(25.8,32.95),(25.8,33.43),(24.98,34.25)])]:
 for a,z in zip(path,path[1:]):
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(.3));t.SetLayer(p.F_Cu);t.SetNetCode(pads[ref,'1'].GetNetCode());b.Add(t)
for path in [[(24.02,34.25),(24.02,32.8)],[(29.73,34.25),(29.73,33.4),(29.2,32.87),(29.2,32),(28.2,32)]]:
 for a,z in zip(path,path[1:]):
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(.3));t.SetLayer(p.F_Cu);t.SetNetCode(pads['U20','2'].GetNetCode());b.Add(t)
# Join the existing +5V_MAIN trunk on In3; preserve its copper geometry.
v=p.PCB_VIA(b);v.SetPosition(vec((28.77,34.8)));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(pads['C1801','1'].GetNetCode());b.Add(v)
t=p.PCB_TRACK(b);t.SetStart(pads['C1801','1'].GetPosition());t.SetEnd(v.GetPosition());t.SetWidth(p.FromMM(.3));t.SetLayer(p.F_Cu);t.SetNetCode(v.GetNetCode());b.Add(t)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'lcd-bypass-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'h8103-hole-drc.json').read_text()),json.loads((D/'lcd-bypass-drc.json').read_text()))
b.BuildConnectivity();pairs=[(('U20','1'),('C1203','1')),(('U20','1'),('C1801','1')),(('U20','5'),('C1802','1')),(('U20','2'),('C1801','2')),(('U20','2'),('C1802','2')),(('U20','2'),('C435','2'))];checks=[]
for a,z in pairs:
 checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'LCD_LOCAL_BYPASS_CONNECTED' if accepted else 'REJECTED_LCD_BYPASS','source_sha256':proof['sha256'],'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'new_violations':new,'checks':checks,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'lcd-bypass.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
