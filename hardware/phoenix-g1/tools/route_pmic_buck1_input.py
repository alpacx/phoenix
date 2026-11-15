#!/usr/bin/env python3
"""Local VCC1 bypass from the accepted VCC2 stage; power integrity unqualified."""
import pcbnew as p,json,hashlib,math,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';D=E/'pmic-inputs/pcb';src=D/'buck2-front.kicad_pcb';cp=json.loads((D/'buck2-front.json').read_text());assert cp['status']=='VCC2_FRONT_BYPASS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];out=D/'buck1-input.kicad_pcb';b=p.LoadBoard(str(src));b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};replaced=[]
def vec(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
paths=[('+3V3_SYS',.127,[(56.59,9.7),(55.85,9.7)]),('+3V3_SYS',.5,[(55.85,9.7),(55.65,9.55)]),('+3V3_SYS',.5,[(54.95,9),(55.65,9.55)]),('GND',.3,[(53.05,9),(52.1,9.95),(52.1,10.5)])]
for net,width,path in paths:
 code=pads['C421','1' if net=='+3V3_SYS' else '2'].GetNetCode()
 for a,z in zip(path,path[1:]):
  tr=p.PCB_TRACK(b);tr.SetStart(vec(a));tr.SetEnd(vec(z));tr.SetWidth(p.FromMM(width));tr.SetLayer(p.F_Cu);tr.SetNetCode(code);b.Add(tr)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'buck1-input-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'buck1-input-drc.json').read_text()));b.BuildConnectivity();connected=pads['C421','1'].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['U4','11'])};result={'status':'VCC1_BYPASS_CONNECTED' if connected and not new else 'REJECTED_FRONT_TRIAL','source_sha256':cp['sha256'],'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'new_violations':new,'input_connected':connected,'replaced_copper':replaced,'electrical_qualified':False,'assembly_ready':False}
if not new and connected:result['preservation']=verify_preservation(p.LoadBoard(str(src)),b,replaced_copper=replaced)
(D/'buck1-input.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
