#!/usr/bin/env python3
"""Connect C470 to the existing SWOUT1 via on B.Cu, geometry only."""
import pcbnew as p,json,shutil,subprocess,math,hashlib
from pathlib import Path
from local_pcb_router import LocalRouter,smd_copper_layer
from drc_regression import introduced
from pcb_preservation import verify_preservation
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-buck5/pcb';src=D/'daughterboard-holes.kicad_pcb';out=D/'io-bypass.kicad_pcb';b=p.LoadBoard(str(src));b.BuildConnectivity();pads={(f.GetReference(),a.GetNumber()):a for f in b.GetFootprints() for a in f.Pads()};s=pads['U4','55'];t=pads['C470','1'];base=json.loads((D/'daughterboard-holes-drc.json').read_text());held=[];records=[];connected_ids={q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(s)}
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
assert smd_copper_layer(t)==p.B_Cu
vias=[v for v in b.GetTracks() if isinstance(v,p.PCB_VIA) and v.m_Uuid.AsString() in connected_ids and v.GetNetname()==t.GetNetname()]
def vec(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
accepted=False
for width in [.5,.4]:
 r=LocalRouter(b,(59,3,67,9),width=width,grid=.025);blocked=r.blocked(p.B_Cu,t.GetNetname());r.max_expansions=60000
 for via in sorted(vias,key=lambda v:math.dist(r.xy(v),r.xy(t))):
  path=r.solve(blocked,r.cell(r.xy(via)),r.cell(r.xy(t)))
  if not path:continue
  path=[r.xy(via)]+path+[r.xy(t)];added=[]
  for a,z in zip(path,path[1:]):
   if math.dist(a,z)<1e-6:continue
   tr=p.PCB_TRACK(b);tr.SetStart(vec(a));tr.SetEnd(vec(z));tr.SetWidth(p.FromMM(width));tr.SetLayer(p.B_Cu);tr.SetNetCode(t.GetNetCode());b.Add(tr);added.append(tr)
  p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'io-bypass-drc.json'),str(out)],check=True,capture_output=True);new=introduced(base,json.loads((D/'io-bypass-drc.json').read_text()));b.BuildConnectivity();connected=t.m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(s)};records.append({'width_mm':width,'path_length_mm':sum(math.dist(a,z) for a,z in zip(path,path[1:])),'new_violations':new,'connected':connected})
  if not new and connected:accepted=True;break
  for tr in added:b.Remove(tr)
  held.extend(added)
 if accepted:break
assert accepted,records
result={'status':'IO_BYPASS_LOCAL_CONNECTIVITY_CHECKED','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'trials':records,'preservation':verify_preservation(p.LoadBoard(str(src)),b),'electrical_qualified':False,'assembly_ready':False};(D/'io-bypass.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
