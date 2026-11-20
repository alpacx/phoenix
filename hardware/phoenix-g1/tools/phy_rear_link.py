"""Check candidate power entry vias with filled zones and physical connectivity."""
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
sites=json.loads((study/'r530-inner-tap-screen.json').read_text())['inner_taps']
for index,(xy,start) in enumerate(sites):
 def point(pos):return p.VECTOR2I(*(p.FromMM(v) for v in pos))
 b=p.LoadBoard(str(src));net=b.GetNetcodeFromNetname('+3V3_IO')
 track=p.PCB_TRACK(b);track.SetStart(point(start));track.SetEnd(point(xy));track.SetWidth(p.FromMM(1.05));track.SetLayer(p.In2_Cu);track.SetNetCode(net);b.Add(track)
 via=p.PCB_VIA(b);via.SetPosition(point(xy));via.SetWidth(p.FromMM(.6));via.SetDrill(p.FromMM(.3));via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNetCode(net);b.Add(via)
 resistor=b.FindFootprintByReference('R530')
 resistor.Flip(resistor.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
 resistor.SetOrientationDegrees(0)
 pad=resistor.FindPadByNumber('1')
 desired=point((xy[0]+.95,xy[1]))
 resistor.Move(desired-pad.GetPosition())
 feed=p.PCB_TRACK(b);feed.SetStart(point(xy));feed.SetEnd(desired);feed.SetWidth(p.FromMM(1.05));feed.SetLayer(p.B_Cu);feed.SetNetCode(net);b.Add(feed)
 folder=study/'runs'/f'phy-rear-link-{index}';folder.mkdir(exist_ok=True)
 for file in ['phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table']:shutil.copy2(base/file,folder/file)
 dest=folder/src.name;p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(dest),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(dest)],check=True,capture_output=True)
 new=introduced(old,json.loads((folder/'drc.json').read_text()))
 b.BuildConnectivity()
 connected=via.m_Uuid.AsString() in {o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('R530').FindPadByNumber('1'))}
 results.append(dict(index=index,position=xy,source=start,connected=connected,violations=new))
(study/'r530-rear-link-drc.json').write_text(json.dumps(results,indent=2)+'\n')
print([(r['index'],len(r['violations'])) for r in results],flush=True);os._exit(0)
