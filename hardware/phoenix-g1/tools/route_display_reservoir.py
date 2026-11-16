#!/usr/bin/env python3
"""Place and connect the existing display rail reservoir capacitor. Geometry/continuity only."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'display-input-returns.kicad_pcb';proof=json.loads((D/'display-input-returns.json').read_text());assert proof['status']=='DISPLAY_INPUT_RETURNS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
b.BuildConnectivity()
f=next(f for f in b.GetFootprints() if f.GetReference()=='C1812')
assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads())
if f.GetLayer()!=p.F_Cu:f.Flip(f.GetPosition(),False)
f.SetPosition(vec((22,35)));f.SetOrientationDegrees(180)
route('+3V0_LCD',.3,[(24.98,34.25),(24.98,35),(22.48,35)])
from local_pcb_router import LocalRouter
r=LocalRouter(b,(18,33,27,38),width=.2,grid=.05)
tree=r.paths_from(r.blocked(p.F_Cu,'GND'),r.cell(r.xy(pads['C1812','2'])),6)
forbidden=set()
for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= r.blocked(layer,'GND',.45,True)
choices=sorted((q for q in tree['distances'] if q not in forbidden),key=tree['distances'].get)
assert choices,(r.xy(pads['C1812','2']),r.cell(r.xy(pads['C1812','2'])) in r.blocked(p.F_Cu,'GND'),len(tree['distances']))
q=choices[0];route('GND',.2,[r.xy(pads['C1812','2'])]+r.path_from_tree(tree,q));via('GND',r.world(q))
out=D/'display-reservoir.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'display-reservoir-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'display-input-returns-drc.json').read_text()),json.loads((D/'display-reservoir-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('C1812','1'),('U20','5')),(('C1812','2'),('U20','2'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'DISPLAY_RESERVOIR_CONNECTED' if accepted else 'REJECTED_DISPLAY_RESERVOIR','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'display-reservoir.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
