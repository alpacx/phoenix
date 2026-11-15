#!/usr/bin/env python3
"""CPU switch/input draft. Widths and via topology require power qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/startup-power/pcb'
src=D/'vcc3.kicad_pcb';proof=json.loads((D/'vcc3.json').read_text());assert proof['status']=='VCC3_BYPASS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()}
assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in fs['U10'].Pads())
fs['U10'].SetOrientationDegrees(180)
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points):
 for a,z in zip(points,points[1:]):
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(p.F_Cu);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
for x in [59.4,59.8]:route('CPU_SW',.2,[(x,21.6),(x,21.2),(x,20.5)])
route('CPU_SW',.2,[(59.4,21.6),(59.8,21.6)])
route('CPU_SW',.5,[(59.4,20.5),(59.8,20.5)])
route('CPU_SW',.8,[(59.8,20.5),(61,19.5),(61,19.43)])
for x in [60.2,60.6]:route('+5V_MAIN',.2,[(x,21.6),(x,21.2)])
route('+5V_MAIN',.2,[(60.2,21.2),(60.6,21.2)])
route('+5V_MAIN',.5,[(60.6,21.2),(61.75,21.2),(62.55,22)])
out=D/'cpu-switch.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'cpu-switch-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'vcc3-drc.json').read_text()),json.loads((D/'cpu-switch-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('U10',n),('L1001','1')) for n in ['D3','D4','E3','E4']]+[(('U10',n),('C1001','1')) for n in ['D1','D2','E1','E2']]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'CPU_SWITCH_INPUT_CONNECTED' if accepted else 'REJECTED_CPU_SWITCH','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'electrical_qualified':False,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'cpu-switch.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
