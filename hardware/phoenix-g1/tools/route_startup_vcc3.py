#!/usr/bin/env python3
"""Rejected VCC3 placement study; never promoted without a passing audit."""
import pcbnew as p,json,hashlib,math,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';S=E/'aux-mount-clear';D=E/'startup-power/pcb';D.mkdir(parents=True,exist_ok=True);cp=json.loads((S/'working-candidate.json').read_text());src=S/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];out=D/'vcc3.kicad_pcb';b=p.LoadBoard(str(src));b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};replaced=[]
def vec(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
f=next(f for f in b.GetFootprints() if f.GetReference()=='C423')
assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads())
f.Flip(f.GetPosition(),False);f.SetPosition(vec((56.1,17.0)));f.SetOrientationDegrees(270)
l=next(f for f in b.GetFootprints() if f.GetReference()=='L1001');assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in l.Pads());l.SetPosition(vec((61.0,17.2)));l.SetOrientationDegrees(270)
paths=[('+3V3_SYS',.127,[(59.3,12.41),(59.3,13.35)]),('+3V3_SYS',.5,[(59.3,13.35),(57.7,13.35),(56.1,16.05)])]
v=p.PCB_VIA(b);v.SetPosition(vec((58.0,17.2)));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(pads['C423','2'].GetNetCode());b.Add(v)
# Reposition the existing Wi-Fi ground via out of the rotated inductor land.
oldvia=next(t for t in b.GetTracks() if t.m_Uuid.AsString()=='72eba6e0-487a-4876-a998-3bc0edbe0318')
assert isinstance(oldvia,p.PCB_VIA) and oldvia.GetNetname()=='GND'
replaced=[oldvia.m_Uuid.AsString()];oldvia.SetPosition(vec((59.4,17.2)))
tr=p.PCB_TRACK(b);tr.SetStart(vec((59.4,15.4)));tr.SetEnd(vec((59.4,17.2)));tr.SetWidth(p.FromMM(.3));tr.SetLayer(p.B_Cu);tr.SetNetCode(oldvia.GetNetCode());b.Add(tr)
paths.append(('GND',.3,[(56.1,17.95),(58.0,17.95),(58.0,17.2)]))
for net,width,path in paths:
 code=pads['C423','1' if net=='+3V3_SYS' else '2'].GetNetCode()
 for a,z in zip(path,path[1:]):
  tr=p.PCB_TRACK(b);tr.SetStart(vec(a));tr.SetEnd(vec(z));tr.SetWidth(p.FromMM(width));tr.SetLayer(p.F_Cu);tr.SetNetCode(code);b.Add(tr)
shutil.copy2(src.parent/'fp-lib-table',D/'fp-lib-table')
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'vcc3-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'vcc3-drc.json').read_text()));b.BuildConnectivity();connected=pads['C423','1'].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['U4','24'])};result={'status':'VCC3_BYPASS_CONNECTED' if connected and not new else 'REJECTED_FRONT_TRIAL','source_sha256':cp['sha256'],'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'new_violations':new,'input_connected':connected,'replaced_copper':replaced,'electrical_qualified':False,'assembly_ready':False}
if not new and connected:result['preservation']=verify_preservation(p.LoadBoard(str(src)),b,replaced_copper=replaced)
(D/'vcc3.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
