#!/usr/bin/env python3
"""Connect display buffer control grounds and CS pull-up supply. Geometry/continuity only."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'display-input-pulls.kicad_pcb';proof=json.loads((D/'display-input-pulls.json').read_text());assert proof['status']=='DISPLAY_INPUT_PULLS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
from local_pcb_router import LocalRouter
r=LocalRouter(b,(25,28,33,35),width=.2,grid=.025)
a=pads['R1815','2'];z=pads['U20','3'];path=r.solve(r.blocked(p.F_Cu,'+3V3_IO'),r.cell(r.xy(a)),r.cell(r.xy(z)));assert path
route('+3V3_IO',.2,[r.xy(a)]+path+[r.xy(z)])
route('GND',.3,[(25.98,27.87),(26.63,27.87),(27.28,27.87),(27.93,27.87)])
for ref,pin in [('U21','1'),('U21','10')]:
 r=LocalRouter(b,(18,20,34,38),width=.2,grid=.05)
 tree=r.paths_from(r.blocked(p.F_Cu,'GND'),r.cell(r.xy(pads[ref,pin])),10)
 forbidden=set()
 for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:
  forbidden |= r.blocked(layer,'GND',.45,True)
 existing={r.cell(r.xy(v)):v for v in b.GetTracks() if isinstance(v,p.PCB_VIA) and v.GetNetname()=='GND'}
 choices=sorted((q for q in tree['distances'] if q not in forbidden or q in existing),key=tree['distances'].get)
 assert choices,('No ground via',ref,pin)
 q=choices[0]
 route('GND',.2,[r.xy(pads[ref,pin])]+r.path_from_tree(tree,q))
 if q not in existing:via('GND',r.world(q))
out=D/'display-input-returns.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'display-input-returns-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'display-input-pulls-drc.json').read_text()),json.loads((D/'display-input-returns-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('U21',pin),('U20','2')) for pin in ['1','7','8','9','10']]+[((ref,'2'),('U20','2')) for ref in ['R1811','R1812','R1813','R1814']]+[(('R1815','2'),('U20','3'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'DISPLAY_INPUT_RETURNS_CONNECTED' if accepted else 'REJECTED_DISPLAY_INPUT_RETURNS','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'display-input-returns.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
