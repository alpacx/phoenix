#!/usr/bin/env python3
"""Remove only the newly added SW5 route to route adjacent VCC9 first."""
import pcbnew as p,json,subprocess,shutil
from pathlib import Path
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-buck5/pcb';src=D/'io-reroute.kicad_pcb';out=D/'input-first.kicad_pcb';b=p.LoadBoard(str(src));held=[]
assert json.loads((D/'io-reroute.json').read_text())['accepted']
for t in list(b.GetTracks()):
 if t.GetNetname()=='PMIC_SW5':b.Remove(t);held.append(t)
assert held
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'input-first-drc.json'),str(out)],check=True,capture_output=True)
assert not introduced(json.loads((D/'feedback-drc.json').read_text()),json.loads((D/'input-first-drc.json').read_text()))
print('Removed only SW5 primitives:',len(held))
