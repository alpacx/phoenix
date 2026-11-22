#!/usr/bin/env python3
"""Isolated ground-return geometry; no current/thermal qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess,os,sys
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel';src=D/'baseline/source.kicad_pcb';out=D/'ground-returns.kicad_pcb';report=D/'ground-returns.json'
assert hashlib.sha256(src.read_bytes()).hexdigest()==json.loads((D/'baseline/checkpoint.json').read_text())['sha256']
if '--verify' in sys.argv:
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'ground-returns-drc.json'),str(out)],check=True,capture_output=True)
 b=p.LoadBoard(str(out));a=p.LoadBoard(str(src));b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
 checks=[]
 for ref in ['C466','C468','C469','C465','C467','C463','C464']:
  q=pads[ref,'2']; connected={v.m_Uuid.AsString() for v in b.GetConnectivity().GetConnectedItems(q)}
  checks.append({'pad':ref+'.2','ground_reference':'C435.2','connected':pads['C435','2'].m_Uuid.AsString() in connected})
 new=introduced(json.loads((D/'baseline/drc.json').read_text()),json.loads((D/'ground-returns-drc.json').read_text()))
 r={'status':'ACCEPTED' if not new and all(x['connected'] for x in checks) else 'REJECTED','checks':checks,'new_violations':new,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'assembly_ready':False,'preservation':verify_preservation(a,b)}
 report.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2),flush=True);os._exit(0)
b=p.LoadBoard(str(src))
def route(points,layer):
 for a,z in zip(points,points[1:]):
  t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(*(p.FromMM(x) for x in a)));t.SetEnd(p.VECTOR2I(*(p.FromMM(x) for x in z)));t.SetLayer(layer);t.SetWidth(p.FromMM(.3));t.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(t)
route([(2.02,26.8),(1.7,27.12),(1.7,28.8)],p.B_Cu)
route([(2.02,34),(2.3,33.72),(2.3,32.25)],p.B_Cu)
route([(4.48,36),(5.3,35.18),(5.3,34)],p.F_Cu)
route([(6.98,36.5),(6.98,35.5),(6.6,35.12),(6.6,34.5)],p.F_Cu)
route([(6.98,38),(6.98,36.5)],p.F_Cu)
route([(9.48,38),(9.48,36.5),(9.48,35.5),(6.98,35.5)],p.F_Cu)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
shutil.copy2(D/'baseline/fp-lib-table',D/'fp-lib-table')
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
os.execv(sys.executable,[sys.executable,__file__,'--verify'])
