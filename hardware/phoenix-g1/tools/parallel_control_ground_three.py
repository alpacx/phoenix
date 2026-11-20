#!/usr/bin/env python3
"""Isolated ground-return geometry; no current/thermal qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess,os,sys
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel';src=D/'ground-returns-two.kicad_pcb';out=D/'ground-returns-three.kicad_pcb';report=D/'ground-returns-three.json'
assert hashlib.sha256(src.read_bytes()).hexdigest()==json.loads((D/'ground-returns-two.json').read_text())['sha256']
if '--verify' in sys.argv:
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'ground-returns-three-drc.json'),str(out)],check=True,capture_output=True)
 b=p.LoadBoard(str(out));a=p.LoadBoard(str(src));b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
 checks=[]
 for ref in ['C1649','C1654','C1671','C1678','C1646']:
  q=pads[ref,'2']; connected={v.m_Uuid.AsString() for v in b.GetConnectivity().GetConnectedItems(q)}
  checks.append({'pad':ref+'.2','ground_reference':'C435.2','connected':pads['C435','2'].m_Uuid.AsString() in connected})
 new=introduced(json.loads((D/'ground-returns-two-drc.json').read_text()),json.loads((D/'ground-returns-three-drc.json').read_text()))
 r={'status':'ACCEPTED' if not new and all(x['connected'] for x in checks) else 'REJECTED','checks':checks,'new_violations':new,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'assembly_ready':False,'preservation':verify_preservation(a,b)}
 report.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2),flush=True);os._exit(0)
b=p.LoadBoard(str(src))
def route(points,layer):
 for a,z in zip(points,points[1:]):
  t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(*(p.FromMM(x) for x in a)));t.SetEnd(p.VECTOR2I(*(p.FromMM(x) for x in z)));t.SetLayer(layer);t.SetWidth(p.FromMM(.3));t.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(t)
route([(21.02,21.5),(19.8,22.72),(19.8,22.8)],p.B_Cu)
route([(21.02,23),(21.02,22.8),(19.8,22.8)],p.B_Cu)
route([(22.02,26.5),(22.02,27.28),(21.45,27.85)],p.B_Cu)
route([(24.05,23),(24.05,22.53),(22.72,21.2)],p.B_Cu)
route([(21.02,20),(20.2,20),(19.85,19.65),(18.2,19.65)],p.B_Cu)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
shutil.copy2(D/'baseline/fp-lib-table',D/'fp-lib-table')
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
os.execv(sys.executable,[sys.executable,__file__,'--verify'])
