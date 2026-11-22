#!/usr/bin/env python3
"""Isolated low-speed LCD data/command connection, existing design rules preserved."""
import pcbnew as p,json,hashlib,shutil,subprocess,os,sys,math
from pathlib import Path
from local_pcb_router import LocalRouter
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel';src=D/'ground-returns-three.kicad_pcb';out=D/'lcd-dc.kicad_pcb';report=D/'lcd-dc.json'
assert hashlib.sha256(src.read_bytes()).hexdigest()==json.loads((D/'ground-returns-three.json').read_text())['sha256']
if '--verify' in sys.argv:
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'lcd-dc-drc.json'),str(out)],check=True,capture_output=True)
 b=p.LoadBoard(str(out));a=p.LoadBoard(str(src));b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};checks=[]
 for ref,num in [('U21','4'),('R1813','1')]:checks.append({'from':'U1.N1','to':ref+'.'+num,'connected':pads[ref,num].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['U1','N1'])}})
 new=introduced(json.loads((D/'ground-returns-three-drc.json').read_text()),json.loads((D/'lcd-dc-drc.json').read_text()))
 r={'status':'ACCEPTED' if not new and all(x['connected'] for x in checks) else 'REJECTED','checks':checks,'new_violations':new,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'assembly_ready':False,'preservation':verify_preservation(a,b)}
 report.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2),flush=True);os._exit(0)
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};name='LCD_DC'
r=LocalRouter(b,(20,16,39,33),width=.2,clearance=.2,grid=.05);r.max_expansions=300000
r.pad_clearances={q.m_Uuid.AsString():.0762 for f in b.GetFootprints() if f.GetReference()=='U1' for q in f.Pads()}
start,end=r.xy(pads['U1','N1']),(24.0,28.675);blocked=r.blocked(p.F_Cu,name);forbidden=set()
for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= r.blocked(layer,name,.45,True)
ta=r.paths_from(blocked,r.cell(start),5);tz=r.paths_from(blocked,r.cell(end),4)
ca=[q for q in sorted(ta['distances'],key=ta['distances'].get) if q not in forbidden][:30];cz=[q for q in sorted(tz['distances'],key=tz['distances'].get) if q not in forbidden][:30]
print('escape choices',len(ca),len(cz),'trees',len(ta['distances']),len(tz['distances']),'blocked',r.cell(start) in blocked,r.cell(end) in blocked,flush=True);found=None
for layer in [p.In4_Cu,p.In1_Cu]:
 mid=r.blocked(layer,name)
 for va in ca:
  for vz in cz:
   path=r.solve(mid,va,vz)
   if path:found=(layer,va,vz,path);break
  if found:break
 if found:break
assert found, 'No lawful 0.2 mm control route'
layer,va,vz,path=found
routes=[(p.F_Cu,[start]+r.path_from_tree(ta,va)),(layer,path),(p.F_Cu,[end]+r.path_from_tree(tz,vz))]
def pt(q):return p.VECTOR2I(*(p.FromMM(v) for v in q))
for layer,points in routes:
 for a,z in zip(points,points[1:]):
  if math.dist(a,z)<1e-7:continue
  t=p.PCB_TRACK(b);t.SetStart(pt(a));t.SetEnd(pt(z));t.SetLayer(layer);t.SetWidth(p.FromMM(.2));t.SetNetCode(b.GetNetcodeFromNetname(name));b.Add(t)
for cell in [va,vz]:
 v=p.PCB_VIA(b);v.SetPosition(pt(r.world(cell)));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetViaType(p.VIATYPE_THROUGH);v.SetNetCode(b.GetNetcodeFromNetname(name));b.Add(v)
(D/'lcd-dc-path.json').write_text(json.dumps({'routes':[(b.GetLayerName(l),pts) for l,pts in routes],'vias':[r.world(va),r.world(vz)]},indent=2)+'\n')
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
os.execv(sys.executable,[sys.executable,__file__,'--verify'])
