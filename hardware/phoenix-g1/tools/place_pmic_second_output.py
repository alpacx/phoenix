#!/usr/bin/env python3
"""Bounded search for the unrouted second BUCK5 capacitor."""
import pcbnew as p,json,subprocess,shutil
from pathlib import Path
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-buck5/pcb';src=D/'feedback-reclosed.kicad_pcb';out=D/'second-output.kicad_pcb';b=p.LoadBoard(str(src));base=json.loads((D/'feedback-reclosed-drc.json').read_text());f=next(f for f in b.GetFootprints() if f.GetReference()=='C445');trials=[]
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
for x,y in [(55.5,7.5),(55.5,6),(55.5,8.5),(57,7.5),(57,8.5),(54.5,7.5)]:
 f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'second-output-drc.json'),str(out)],check=True,capture_output=True);new=introduced(base,json.loads((D/'second-output-drc.json').read_text()));trials.append({'position':[x,y],'new_violations':new});print(x,y,len(new),flush=True)
 if not new:break
(D/'second-output.json').write_text(json.dumps({'accepted':not new,'trials':trials,'assembly_ready':False},indent=2)+'\n')
