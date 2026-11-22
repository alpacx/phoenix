#!/usr/bin/env python3
"""Preserve UUIDs while moving two newly introduced RAM vias clear of all SMT pads."""
import pcbnew as p,json,shutil,os,sys,subprocess,hashlib
from pathlib import Path
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel'
MOVES=[((23.8,20.5),(23.3,20.6)),((23.3,17),(23.15,17))]
def v(q):return p.VECTOR2I(*(p.FromMM(x) for x in q))
def patch(board):
 changed=[]
 for old,new in MOVES:
  matches=[t for t in board.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetPosition()==v(old) and t.GetNetname()=='GND']
  if not matches:continue
  assert len(matches)==1
  via=matches[0];via.SetPosition(v(new));changed.append(via.m_Uuid.AsString())
  for t in board.GetTracks():
   if isinstance(t,p.PCB_VIA) or t.GetNetname()!='GND':continue
   if t.GetStart()==v(old):t.SetStart(v(new));changed.append(t.m_Uuid.AsString())
   if t.GetEnd()==v(old):t.SetEnd(v(new));changed.append(t.m_Uuid.AsString())
 return changed
if '--verify' in sys.argv:
 out=D/'via-pad-correction-trial.kicad_pcb';dr=D/'via-pad-correction-trial-drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],check=True,capture_output=True)
 new=introduced(json.loads((D/'right-ground-vias-drc.json').read_text()),json.loads(dr.read_text()));print(json.dumps(new,indent=2),flush=True);os._exit(bool(new))
b=p.LoadBoard(str(D/'right-ground-vias.kicad_pcb'));changes=patch(b);assert len(changes)==4
out=D/'via-pad-correction-trial.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(D/('right-ground-vias.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);(D/'via-pad-correction-uuids.json').write_text(json.dumps(changes,indent=2)+'\n');os.execv(sys.executable,[sys.executable,__file__,'--verify'])
