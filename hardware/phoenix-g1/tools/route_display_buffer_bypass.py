#!/usr/bin/env python3
"""Connect the display buffer local bypass and ground. Geometry/continuity only."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'display-enable.kicad_pcb';proof=json.loads((D/'display-enable.json').read_text());assert proof['status']=='DISPLAY_ENABLE_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
b.BuildConnectivity()
f=next(f for f in b.GetFootprints() if f.GetReference()=='C1811')
assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads())
f.SetPosition(vec((21.1,22)));f.SetOrientationDegrees(90)
route('+3V0_LCD',.3,[(22.07,22.13),(21.45,22.13),(21.1,22.48)])
route('GND',.3,[(21.1,21.52),(21.1,20.9),(22.72,20.9),(22.72,21.2)])
route('GND',.3,[(22.72,22.13),(22.72,21.2)])
via('GND',(22.72,21.2))
out=D/'display-buffer-bypass.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'display-buffer-bypass-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'display-enable-drc.json').read_text()),json.loads((D/'display-buffer-bypass-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('U21','20'),('C1811','1')),(('U21','19'),('C1811','2')),(('C1811','2'),('U20','2'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'DISPLAY_BUFFER_BYPASS_CONNECTED' if accepted else 'REJECTED_DISPLAY_BUFFER_BYPASS','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'display-buffer-bypass.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
