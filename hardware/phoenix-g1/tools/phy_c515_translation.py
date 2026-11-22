"""Test C515 translations with full-width supply and ground connections."""
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
for dx,dy in [(0,-.5),(0,.5),(-.5,0),(.5,0),(0,-1),(0,1),(-1,0),(1,0),(-.5,-.5),(.5,-.5),(-.5,.5),(.5,.5)]:
 b=p.LoadBoard(str(src))
 cap=b.FindFootprintByReference('C515')
 previous={q.GetNumber():q.GetPosition() for q in cap.Pads()}
 cap.Move(p.VECTOR2I(p.FromMM(dx),p.FromMM(dy)))
 for pad in cap.Pads():
  track=p.PCB_TRACK(b)
  track.SetStart(pad.GetPosition())
  track.SetEnd(previous[pad.GetNumber()])
  track.SetLayer(p.F_Cu)
  track.SetNet(pad.GetNet())
  track.SetWidth(p.FromMM(1.05 if pad.GetNumber()=='1' else .5))
  b.Add(track)
 folder=study/'runs'/f'c515-translation-{dx}-{dy}';folder.mkdir(exist_ok=True)
 for file in ['phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table']:shutil.copy2(base/file,folder/file)
 dest=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(dest),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(dest)],check=True,capture_output=True)
 new=introduced(old,json.loads((folder/'drc.json').read_text()))
 results.append(dict(dx=dx,dy=dy,violations=new))
(study/'c515-translation-results.json').write_text(json.dumps(results,indent=2)+'\n')
print([((r['dx'],r['dy']),len(r['violations'])) for r in results],flush=True);os._exit(0)
