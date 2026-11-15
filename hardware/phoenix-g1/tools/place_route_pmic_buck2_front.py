#!/usr/bin/env python3
"""VCC2 bypass on front: explicit local geometry, no current/stability qualification."""
import pcbnew as p,json,hashlib,math,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';B=E/'pmic-buck5';cp=json.loads((B/'working-candidate.json').read_text());src=B/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];D=E/'pmic-inputs/pcb';D.mkdir(parents=True,exist_ok=True);out=D/'buck2-front.kicad_pcb';b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()};pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};held=[]
def vec(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in fs['R1814'].Pads())
fs['R1814'].SetPosition(vec((51,10.5)))
old=list(b.GetConnectivity().GetConnectedTracks(pads['C422','2']));assert len(old)==1 and old[0].GetLayer()==p.B_Cu and old[0].GetNetname()=='GND'
replaced=[q.m_Uuid.AsString() for q in old]
for q in old:b.Remove(q);held.append(q)
f=fs['C422'];f.Flip(f.GetPosition(),False);f.SetPosition(vec((54,11.5)));f.SetOrientationDegrees(180)
paths=[('+3V3_SYS',.127,[(56.59,9.35),(55.85,9.35)]),('+3V3_SYS',.5,[(55.85,9.35),(55.65,9.55),(55.65,10.8),(54.95,11.5)]),('GND',.3,[(53.05,11.5),(52.1,10.55),(52.1,10.5)])]
for net,width,path in paths:
 code=pads['C422','1' if net=='+3V3_SYS' else '2'].GetNetCode()
 for a,z in zip(path,path[1:]):
  tr=p.PCB_TRACK(b);tr.SetStart(vec(a));tr.SetEnd(vec(z));tr.SetWidth(p.FromMM(width));tr.SetLayer(p.F_Cu);tr.SetNetCode(code);b.Add(tr)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
shutil.copy2(src.parent/'fp-lib-table',D/'fp-lib-table');p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'buck2-front-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'buck2-front-drc.json').read_text()));b.BuildConnectivity();connected=pads['C422','1'].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['U4','10'])};result={'status':'VCC2_FRONT_BYPASS_CONNECTED' if connected and not new else 'REJECTED_FRONT_TRIAL','source_sha256':cp['sha256'],'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'new_violations':new,'input_connected':connected,'replaced_copper':replaced,'electrical_qualified':False,'assembly_ready':False}
if not new and connected:result['preservation']=verify_preservation(p.LoadBoard(str(src)),b,replaced_copper=replaced)
(D/'buck2-front.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
