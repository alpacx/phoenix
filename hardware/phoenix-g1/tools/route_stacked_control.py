#!/usr/bin/env python3
"""Local low-current accessory eFuse controls, not the modem power path."""
import pcbnew as p,json,math,shutil,hashlib
from pathlib import Path
from local_pcb_router import LocalRouter
R=Path(__file__).resolve().parents[1];O=R/'migration-rk3562/experiments/stacked-expansion';D=O/'pcb';b=p.LoadBoard(str(D/'mount-protected.kicad_pcb'))
fps={f.GetReference():f for f in b.GetFootprints()}
positions={'C8103':(79,4.2,180),'R8103':(82.5,9.5,0),'C8101':(79.8,7.7,0),'C8102':(74,8,180),'R8101':(74,4.7,0),'R8102':(73,6.5,180)}
for ref,(x,y,angle) in positions.items():
 f=fps[ref];f.SetOrientationDegrees(angle);f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)))
pads={(f.GetReference(),a.GetNumber()):a for f in b.GetFootprints() for a in f.Pads()};records=[]
def pt(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
for pin,ref in [('7','R8101'),('1','C8103'),('2','R8103'),('6','R8102')]:
 a,z=pads['U8101',pin],pads[ref,'1'];name=a.GetNetname();assert z.GetNetname()==name
 r=LocalRouter(b,(70,2,84,11),width=.2);path=r.solve(r.blocked(p.B_Cu,name),r.cell(r.xy(a)),r.cell(r.xy(z)))
 if not path:records.append({'net':name,'routed':False});continue
 path=[r.xy(a)]+path+[r.xy(z)]
 for x,y in zip(path,path[1:]):
  if math.dist(x,y)<1e-6:continue
  t=p.PCB_TRACK(b);t.SetStart(pt(x));t.SetEnd(pt(y));t.SetLayer(p.B_Cu);t.SetWidth(p.FromMM(.2));t.SetNetCode(a.GetNetCode());b.Add(t)
 b.BuildConnectivity();assert z.m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(a)}
 records.append({'net':name,'routed':True,'endpoints':['U8101.'+pin,ref+'.1'],'length_mm':sum(math.dist(x,y) for x,y in zip(path,path[1:]))})
assert len(records)==4 and all(r['routed'] for r in records),records
p.ZONE_FILLER(b).Fill(b.Zones());dest=D/'control-routed.kicad_pcb';p.SaveBoard(str(dest),b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(D/f'candidate.{ext}',dest.with_suffix('.'+ext))
(D/'control-routed.json').write_text(json.dumps({'status':'LOCAL_CONTROL_ONLY_PENDING_DRC','routes':records,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'placement_changes':positions,'power_path_complete':False,'USB_routed':False,'assembly_ready':False},indent=2)+'\n');print(json.dumps(records))
