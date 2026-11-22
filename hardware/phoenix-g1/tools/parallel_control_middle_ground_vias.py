#!/usr/bin/env python3
"""Isolated ground-return geometry; no current/thermal qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess,os,sys
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel';src=D/'ram-ground-vias.kicad_pcb';out=D/'middle-ground-vias.kicad_pcb';report=D/'middle-ground-vias.json'
assert hashlib.sha256(src.read_bytes()).hexdigest()==json.loads((D/'ram-ground-vias.json').read_text())['sha256']
if '--verify' in sys.argv:
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'middle-ground-vias-drc.json'),str(out)],check=True,capture_output=True)
 b=p.LoadBoard(str(out));a=p.LoadBoard(str(src));b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
 checks=[]
 for ref in ['C1633','C1673','C1624','C1656','C1651','C1619','C1652','C1620','C1675','C1655','C1662','C1623','C1647']:
  q=pads[ref,'2']; connected={v.m_Uuid.AsString() for v in b.GetConnectivity().GetConnectedItems(q)}
  checks.append({'pad':ref+'.2','ground_reference':'C435.2','connected':pads['C435','2'].m_Uuid.AsString() in connected})
 new=introduced(json.loads((D/'ram-ground-vias-drc.json').read_text()),json.loads((D/'middle-ground-vias-drc.json').read_text()))
 r={'status':'ACCEPTED' if not new and all(x['connected'] for x in checks) else 'REJECTED','checks':checks,'new_violations':new,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'assembly_ready':False,'preservation':verify_preservation(a,b)}
 report.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2),flush=True);os._exit(0)
b=p.LoadBoard(str(src))
def route(points,layer):
 for a,z in zip(points,points[1:]):
  t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(*(p.FromMM(x) for x in a)));t.SetEnd(p.VECTOR2I(*(p.FromMM(x) for x in z)));t.SetLayer(layer);t.SetWidth(p.FromMM(.3));t.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(t)
for a,z in [((32.02,25),(31.3,25)),((27.02,26.5),(26.3,26.5)),((31.05,23),(31.05,24.3)),((28.02,23),(28.02,23.95)),((27.52,18.5),(27.52,17.75)),((31.55,27),(30.5,27)),((28.02,21.5),(28.02,20.75)),((31.05,20),(30.0,20)),((29.52,25),(29.52,25.75)),((28.02,17),(27.3,17)),((27.02,25),(26.3,25)),((31.05,17),(30.0,17)),((28.02,20),(27.4,19.25))]:
 route([a,z],p.B_Cu)
 v=p.PCB_VIA(b);v.SetPosition(p.VECTOR2I(*(p.FromMM(x) for x in z)));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetViaType(p.VIATYPE_THROUGH);v.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(v)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
shutil.copy2(D/'baseline/fp-lib-table',D/'fp-lib-table')
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
os.execv(sys.executable,[sys.executable,__file__,'--verify'])
