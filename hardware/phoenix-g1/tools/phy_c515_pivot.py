"""Keep C515 input contact fixed while testing rotated ground pad and return."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess
import pcbnew as p
from drc_regression import introduced
study=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=study/'runs/input-ground-local-002'
src=base/'phy-joint.kicad_pcb'
assert hashlib.sha256(src.read_bytes()).hexdigest()==json.loads((base/'report.json').read_text())['candidate_sha256']
old=json.loads((base/'drc.json').read_text())
results=[]
for degrees in (-90,90,180):
 b=p.LoadBoard(str(src));cap=b.FindFootprintByReference('C515');ground=cap.FindPadByNumber('2')
 before=ground.GetPosition()
 cap.Rotate(cap.FindPadByNumber('1').GetPosition(),p.EDA_ANGLE(degrees,p.DEGREES_T))
 # Retain existing GND copper and restore the local return at its original width.
 track=p.PCB_TRACK(b);track.SetStart(ground.GetPosition());track.SetEnd(before)
 track.SetLayer(p.F_Cu);track.SetNet(ground.GetNet());track.SetWidth(p.FromMM(.5));b.Add(track)
 folder=study/'runs'/f'c515-input-pivot-{degrees}';folder.mkdir(exist_ok=True)
 for file in ['phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table']:shutil.copy2(base/file,folder/file)
 dest=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(dest),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(dest)],check=True,capture_output=True)
 new=introduced(old,json.loads((folder/'drc.json').read_text()))
 results.append(dict(degrees=degrees,violations=new))
(study/'c515-input-pivot-results.json').write_text(json.dumps(results,indent=2)+'\n')
print([(r['degrees'],len(r['violations'])) for r in results],flush=True);os._exit(0)
