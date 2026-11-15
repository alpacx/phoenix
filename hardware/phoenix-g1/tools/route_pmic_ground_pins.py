#!/usr/bin/env python3
"""Ten local RK809 ground necks; bounded fine-pitch geometry, not current qualification."""
import pcbnew as p,json,hashlib,math,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';D=E/'pmic-inputs/pcb';src=D/'buck4-input.kicad_pcb';cp=json.loads((D/'buck4-input.json').read_text());assert cp['status']=='VCC4_BYPASS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];out=D/'pmic-ground-pins.kicad_pcb';b=p.LoadBoard(str(src));b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};replaced=[]
def vec(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
targets={'14':(57.33,10.75),'15':(57.33,11.1),'16':(57.33,11.45),'17':(57.5,11.5),'19':(57.55,11.67),'40':(62.67,10.05),'47':(62.67,7.6),'56':(61.4,6.33),'62':(59.3,6.33),'63':(58.95,6.33)}
for number,end in targets.items():
 pad=pads['U4',number];assert pad.GetNetname()=='GND'
 tr=p.PCB_TRACK(b);tr.SetStart(pad.GetPosition());tr.SetEnd(vec(end));tr.SetWidth(p.FromMM(.15));tr.SetLayer(p.F_Cu);tr.SetNetCode(pad.GetNetCode());b.Add(tr)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
rule='\n(rule "RK809 ground pad neck - electrical qualification pending" (condition "A.NetName == \'GND\' && A.Type == \'Track\' && A.intersectsCourtyard(\'U4\')") (constraint track_width (min 0.15mm)))\n'
out.with_suffix('.kicad_dru').write_text(out.with_suffix('.kicad_dru').read_text()+rule)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'pmic-ground-pins-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'pmic-ground-pins-drc.json').read_text()));b.BuildConnectivity();connected=pads['C435','2'].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['U4','14'])};result={'status':'PMIC_GROUND_PINS_CONNECTED' if connected and not new else 'REJECTED_FRONT_TRIAL','source_sha256':cp['sha256'],'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'new_violations':new,'input_connected':connected,'replaced_copper':replaced,'electrical_qualified':False,'assembly_ready':False}
if not new and connected:result['preservation']=verify_preservation(p.LoadBoard(str(src)),b,replaced_copper=replaced)
(D/'pmic-ground-pins.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
