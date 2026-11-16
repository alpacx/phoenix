#!/usr/bin/env python3
"""Connect remaining Ethernet configuration and bias resistor ground returns; no PHY qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'ethernet-center-tap.kicad_pcb';proof=json.loads((D/'ethernet-center-tap.json').read_text());assert proof['status']=='ETHERNET_CENTER_TAP_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
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
for ref,pin in [('R513','2'),('R528','2'),('R529','2')]:
 r=LocalRouter(b,(52,24,76,39),width=.2,grid=.05)
 tree=r.paths_from(r.blocked(p.F_Cu,'GND'),r.cell(r.xy(pads[ref,pin])),3)
 forbidden=set()
 for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= r.blocked(layer,'GND',.45,True)
 choices=sorted((q for q in tree['distances'] if q not in forbidden),key=tree['distances'].get)
 assert choices,('ground escape blocked',ref)
 q=choices[0];route('GND',.2,[r.xy(pads[ref,pin])]+r.path_from_tree(tree,q));via('GND',r.world(q))
out=D/'ethernet-bias-grounds.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'ethernet-bias-grounds-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'ethernet-center-tap-drc.json').read_text()),json.loads((D/'ethernet-bias-grounds-drc.json').read_text()));b.BuildConnectivity()
pairs=[((ref,pin),('U20','2')) for ref,pin in [('R513','2'),('R528','2'),('R529','2')]]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'ETHERNET_BIAS_GROUNDS_CONNECTED' if accepted else 'REJECTED_ETHERNET_BIAS_GROUNDS','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'ethernet-bias-grounds.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
