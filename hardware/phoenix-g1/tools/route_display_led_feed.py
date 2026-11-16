#!/usr/bin/env python3
"""Connect the existing backlight current-limiting resistor to the 5 V rail. Geometry/continuity only."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'five-volt-testpoint.kicad_pcb';proof=json.loads((D/'five-volt-testpoint.json').read_text());assert proof['status']=='FIVE_VOLT_TESTPOINT_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
route('+5V_MAIN',.3,[(30.175,22),(30.2,22),(30.2,26.05),(28.5,27.75),(28.5,29.15),(27.3,30.35),(27.3,32.65),(28.65,34),(28.65,34.05),(28.7,34.1),(28.7,34.2),(28.75,34.25),(28.77,34.25)])
out=D/'display-led-feed.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'display-led-feed-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'five-volt-testpoint-drc.json').read_text()),json.loads((D/'display-led-feed-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('R1803','1'),('C1801','1'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'DISPLAY_LED_FEED_CONNECTED' if accepted else 'REJECTED_DISPLAY_LED_FEED','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'display-led-feed.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
