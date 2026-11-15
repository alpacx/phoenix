#!/usr/bin/env python3
"""Local VCC4 bypass; power integrity and return-loop impedance unqualified."""
import pcbnew as p,json,hashlib,math,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';D=E/'pmic-inputs/pcb';src=D/'buck1-input.kicad_pcb';cp=json.loads((D/'buck1-input.json').read_text());assert cp['status']=='VCC1_BYPASS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];out=D/'buck4-input.kicad_pcb';b=p.LoadBoard(str(src));b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};replaced=[]
def vec(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
paths=[('+3V3_SYS',.127,[(63.41,8.3),(64.15,8.3)]),('+3V3_SYS',.5,[(64.15,8.3),(64.5,7.95),(64.5,7.55),(65.55,6.5)]),('GND',.3,[(67.45,6.5),(67.45,5.7),(66.85,5.1),(65.45,5.1),(65.3,5.25)])]
for net,width,path in paths:
 code=pads['C424','1' if net=='+3V3_SYS' else '2'].GetNetCode()
 for a,z in zip(path,path[1:]):
  tr=p.PCB_TRACK(b);tr.SetStart(vec(a));tr.SetEnd(vec(z));tr.SetWidth(p.FromMM(width));tr.SetLayer(p.F_Cu);tr.SetNetCode(code);b.Add(tr)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'buck4-input-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'buck4-input-drc.json').read_text()));b.BuildConnectivity();connected=pads['C424','1'].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['U4','45'])};result={'status':'VCC4_BYPASS_CONNECTED' if connected and not new else 'REJECTED_FRONT_TRIAL','source_sha256':cp['sha256'],'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'new_violations':new,'input_connected':connected,'replaced_copper':replaced,'electrical_qualified':False,'assembly_ready':False}
if not new and connected:result['preservation']=verify_preservation(p.LoadBoard(str(src)),b,replaced_copper=replaced)
(D/'buck4-input.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
