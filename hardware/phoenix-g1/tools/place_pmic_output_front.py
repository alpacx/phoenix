#!/usr/bin/env python3
"""Place first BUCK5 output capacitor beside the inductor; preserve prior routing."""
import pcbnew as p,shutil,json,subprocess
from pathlib import Path
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-buck5/pcb';src=D/'grounds.kicad_pcb';out=D/'output-front.kicad_pcb';b=p.LoadBoard(str(src));f=next(f for f in b.GetFootprints() if f.GetReference()=='C435')
assert not any(b.GetConnectivity().GetConnectedTracks(a) for a in f.Pads())
f.Flip(f.GetPosition(),False);f.SetPosition(p.VECTOR2I(p.FromMM(57.3),p.FromMM(1.4)));f.SetOrientationDegrees(180)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'output-front-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'grounds-drc.json').read_text()),json.loads((D/'output-front-drc.json').read_text()));print(json.dumps(new));assert not new
