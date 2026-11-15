#!/usr/bin/env python3
"""PMIC exposed-pad ground-via candidate; thermal performance unqualified: explicit local geometry, no current/stability qualification."""
import pcbnew as p,json,hashlib,math,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';D=E/'pmic-inputs/pcb';src=D/'buck1-input.kicad_pcb';cp=json.loads((D/'buck1-input.json').read_text());assert cp['status']=='VCC1_BYPASS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];out=D/'pmic-ground.kicad_pcb';b=p.LoadBoard(str(src));b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};replaced=[]
def vec(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
for x in [59,60,61]:
 for y in [8,9,10]:
  via=p.PCB_VIA(b);via.SetPosition(vec((x,y)));via.SetWidth(p.FromMM(.45));via.SetDrill(p.FromMM(.2));via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNetCode(pads['U4','69'].GetNetCode());b.Add(via)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'pmic-ground-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'pmic-ground-drc.json').read_text()));b.BuildConnectivity();connected=pads['C435','2'].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['U4','69'])};result={'status':'PMIC_EXPOSED_PAD_GROUNDED' if connected and not new else 'REJECTED_FRONT_TRIAL','source_sha256':cp['sha256'],'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'new_violations':new,'input_connected':connected,'replaced_copper':replaced,'electrical_qualified':False,'assembly_ready':False}
if not new and connected:result['preservation']=verify_preservation(p.LoadBoard(str(src)),b,replaced_copper=replaced)
(D/'pmic-ground.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
