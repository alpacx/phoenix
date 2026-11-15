#!/usr/bin/env python3
"""System buck local power copper, explicitly not current/thermal qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/system-3v3/pcb'
src=D/'local-power.kicad_pcb';proof=json.loads((D/'local-power.json').read_text());assert proof['status']=='SYSTEM_LOCAL_POWER_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
# Preserve both endpoints while opening a corridor for voltage sense.
replaced=['52e0331e-9733-468d-aa1a-f5c192bc9fcd'];held=[]
for t in list(b.GetTracks()):
 if t.m_Uuid.AsString() in replaced:b.Remove(t);held.append(t)
assert len(held)==1
route('CC_VBUS_SERIES_2',p.ToMM(held[0].GetWidth()),[(14.95,28.15),(14.1,27.3),(12.85,27.3),(12,28.15)])
from local_pcb_router import LocalRouter
routes=[]
def xy(pad):return (p.ToMM(pad.GetPosition().x),p.ToMM(pad.GetPosition().y))
def connect(a,z,layer_a=p.F_Cu,layer_z=p.F_Cu):
 net=pads[a].GetNetname();assert net==pads[z].GetNetname()
 router=LocalRouter(b,(9,26,23,39.3),width=.2,clearance=.2,grid=.05)
 start,end=xy(pads[a]),xy(pads[z]); print('Routing',a,z,flush=True)
 if layer_a==layer_z:
  direct=router.solve(router.blocked(layer_a,net),router.cell(start),router.cell(end))
  if direct:
   route(net,.2,[start]+direct+[end],layer_a);routes.append({'from':'.'.join(a),'to':'.'.join(z),'layer':b.GetLayerName(layer_a),'path':direct});return
 forbidden=set()
 for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= router.blocked(layer,net,.45,True)
 ta=router.paths_from(router.blocked(layer_a,net),router.cell(start),6.5)
 tz=router.paths_from(router.blocked(layer_z,net),router.cell(end),6.5)
 print('Escape tree',a,len(ta['distances']), 'startblocked',router.cell(start) in router.blocked(layer_a,net),flush=True)
 ca=[q for q in sorted(ta['distances'],key=ta['distances'].get) if q not in forbidden][:30]
 cz=[q for q in sorted(tz['distances'],key=tz['distances'].get) if q not in forbidden][:30]
 for inner in [p.In1_Cu,p.In4_Cu]:
  blocked=router.blocked(inner,net)
  for va in ca:
   for vz in cz:
    if __import__('math').dist(router.world(va),router.world(vz))<.7:continue
    path=router.solve(blocked,va,vz)
    if not path:continue
    pa=[start]+router.path_from_tree(ta,va);pz=[end]+router.path_from_tree(tz,vz)
    route(net,.2,pa,layer_a);route(net,.2,pz,layer_z)
    via(net,router.world(va));via(net,router.world(vz));route(net,.2,path,inner)
    routes.append({'from':'.'.join(a),'to':'.'.join(z),'layer':b.GetLayerName(inner),'path':path,'escape_a':pa,'escape_z':pz});return
 raise RuntimeError(('No safe local control path',a,z,len(ca),len(cz)))
# All four routes carry control/sense current, never system load current.
connect(('U17','9'),('C1303','1'),p.F_Cu,p.B_Cu)
connect(('U17','4'),('R1301','1'))
connect(('U17','14'),('C1305','1'))
connect(('R1301','2'),('C1305','1'))
# SS capacitor return drops directly into the existing ground plane.
router=LocalRouter(b,(15,26,19,30),width=.2,clearance=.2,grid=.05)
forbidden=set()
for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= router.blocked(layer,'GND',.45,True)
start=xy(pads[('C1303','2')]);tree=router.paths_from(router.blocked(p.B_Cu,'GND'),router.cell(start),3)
cell=next(q for q in sorted(tree['distances'],key=tree['distances'].get) if q not in forbidden)
path=[start]+router.path_from_tree(tree,cell);route('GND',.2,path,p.B_Cu);via('GND',router.world(cell))
routes.append({'from':'C1303.2','to':'GND plane','layer':'B.Cu','path':path})
out=D/'control.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'control-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'local-power-drc.json').read_text()),json.loads((D/'control-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('U17','9'),('C1303','1')),(('U17','4'),('R1301','1')),(('U17','14'),('C1305','1')),(('R1301','2'),('C1305','1')),(('C1303','2'),('C1301','2'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'SYSTEM_CONTROL_CONNECTED' if accepted else 'REJECTED_SYSTEM_CONTROL','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'routes':routes,'replaced_copper':replaced,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b,replaced_copper=replaced)
(D/'control.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
