#!/usr/bin/env python3
"""Connect the existing Ethernet center-tap capacitor; isolation and EMC not qualified."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'ethernet-strap-grounds.kicad_pcb';proof=json.loads((D/'ethernet-strap-grounds.json').read_text());assert proof['status']=='ETHERNET_STRAP_GROUNDS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
b.BuildConnectivity()
from local_pcb_router import LocalRouter
pairs=[(('J2','P1'),('C531','1'))]
for start,end in pairs:
 net=pads[start].GetNetname();r=LocalRouter(b,(66,23,84,33),width=.3,grid=.025)
 path=r.solve(r.blocked(p.F_Cu,net),r.cell(r.xy(pads[start])),r.cell(r.xy(pads[end])))
 if path:
  route(net,.3,[r.xy(pads[start])]+path+[r.xy(pads[end])]);continue
 forbidden=set()
 for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= r.blocked(layer,net,.45,True)
 trees=[r.paths_from(r.blocked(p.F_Cu,net),r.cell(r.xy(pads[q])),5) for q in [start,end]]
 candidates=[]
 for tree in trees:
  legal=sorted((q for q in tree['distances'] if q not in forbidden),key=tree['distances'].get)
  spaced=[]
  for q in legal:
   if all((q[0]-v[0])**2+(q[1]-v[1])**2>=(.3/r.grid)**2 for v in spaced):spaced.append(q)
   if len(spaced)==12:break
  candidates.append(spaced)
 assert all(candidates),('no legal front escape',start,end,[len(x) for x in candidates])
 solution=None
 for layer in [p.In4_Cu,p.In2_Cu,p.B_Cu]:
  blocked=r.blocked(layer,net)
  for x in candidates[0]:
   for y in candidates[1]:
    middle=r.solve(blocked,x,y)
    if middle:solution=(layer,x,y,middle);break
   if solution:break
  if solution:break
 assert solution,('no internal bridge',start,end)
 layer,x,y,middle=solution
 route(net,.3,[r.xy(pads[start])]+r.path_from_tree(trees[0],x));via(net,r.world(x))
 route(net,.3,[r.xy(pads[end])]+r.path_from_tree(trees[1],y));via(net,r.world(y))
 route(net,.3,middle,layer)
for ref,pin in [('C531','2')]:
 r=LocalRouter(b,(66,23,84,33),width=.3,grid=.05)
 tree=r.paths_from(r.blocked(p.F_Cu,'GND'),r.cell(r.xy(pads[ref,pin])),5)
 forbidden=set()
 for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= r.blocked(layer,'GND',.45,True)
 choices=sorted((q for q in tree['distances'] if q not in forbidden),key=tree['distances'].get)
 assert choices,('ground escape blocked',ref)
 q=choices[0];route('GND',.2,[r.xy(pads[ref,pin])]+r.path_from_tree(tree,q));via('GND',r.world(q))
pairs += [(('C531','2'),('U20','2'))]
out=D/'ethernet-center-tap.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'ethernet-center-tap-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'ethernet-strap-grounds-drc.json').read_text()),json.loads((D/'ethernet-center-tap-drc.json').read_text()));b.BuildConnectivity()

checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'ETHERNET_CENTER_TAP_CONNECTED' if accepted else 'REJECTED_ETHERNET_CENTER_TAP','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'ethernet-center-tap.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
