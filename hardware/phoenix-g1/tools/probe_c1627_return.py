#!/usr/bin/env python3
"""Sequential isolated C1627 ground-return probe; never updates main checkpoint."""
import pcbnew as p,json,shutil,os,sys,subprocess
from pathlib import Path
from parallel_control_apply_right_ground_vias_delta import apply
from drc_regression import introduced
R=Path(__file__).resolve().parents[1];D=R/'migration-rk3562/experiments/control-routing-parallel';M=D.parent/'pmic-ldo-inputs/pcb';T=D/'c1627-return';T.mkdir(exist_ok=True)
if '--verify' in sys.argv:
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(T/'trial-drc.json'),str(T/'trial.kicad_pcb')],check=True,capture_output=True)
 new=introduced(json.loads((T/'baseline-drc.json').read_text()),json.loads((T/'trial-drc.json').read_text()))
 (T/'result.json').write_text(json.dumps({'new_violations':new,'accepted_drc':not new,'assembly_ready':False},indent=2)+'\n');print(new,flush=True);os._exit(bool(new))
for ext in ['kicad_pcb','kicad_pro','kicad_dru']:shutil.copy2(M/('parallel-local-copper.'+ext),T/('trial.'+ext))
shutil.copy2(M/'parallel-local-copper-drc.json',T/'baseline-drc.json')
shutil.copy2(D/'fp-lib-table',T/'fp-lib-table')
shutil.copy2(T/'trial.kicad_pcb',T/'baseline.kicad_pcb')
b=p.LoadBoard(str(T/'trial.kicad_pcb'));o=json.loads((D/'right-ground-vias-delta.json').read_text());o['tracks']=[t for t in o['tracks'] if [49.3,28] in [t['start_mm'],t['end_mm']]];o['checks']=[c for c in o['checks'] if c['from']=='C1627.2']
for t in o['tracks']:
 for k in ['start_mm','end_mm']:
  if t[k]==[49.3,28]:t[k]=[50.65,29.75]
(T/'delta.json').write_text(json.dumps(o,indent=2)+'\n');apply(b,T/'delta.json');p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(T/'trial.kicad_pcb'),b);os.execv(sys.executable,[sys.executable,__file__,'--verify'])
