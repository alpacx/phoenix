#!/usr/bin/env python3
"""Connect PHY clock using one back-side XIN bridge and a front XOUT route; unqualified oscillator."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'ethernet-clock-grounds.kicad_pcb';proof=json.loads((D/'ethernet-clock-grounds.json').read_text());assert proof['status']=='ETHERNET_CLOCK_GROUNDS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if vec(a)==vec(z):continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
held=[];replaced=[]
for t in list(b.GetTracks()):
 if t.m_Uuid.AsString()=='b4c6e2aa-1c7c-4131-a42a-1d73c70f0ee9':
  assert t.GetNetname()=='+5V_MAIN' and t.GetLayer()==p.In2_Cu and t.GetWidth()==p.FromMM(.8)
  assert {tuple(t.GetStart()),tuple(t.GetEnd())}=={tuple(vec((60.5,24.5))),tuple(vec((60.5,32.95)))}
  b.Remove(t);held.append(t);replaced.append(t.m_Uuid.AsString())
assert len(replaced)==1
route('+5V_MAIN',.8,[(60.5,24.5),(60.9,24.9),(60.9,32.55),(60.5,32.95)],p.In2_Cu)
b.BuildConnectivity()
from local_pcb_router import LocalRouter
pairs=[(('U5','36'),('Y501','1')),(('U5','37'),('Y501','3'))]
for start,check_end in pairs:
 net=pads[start].GetNetname()
 if start==('U5','36'):
  r=LocalRouter(b,(55,27,65,39),width=.2,grid=.025)
  escape=(59.875,31.0);route(net,.15,[r.xy(pads[start]),(60,31.2),escape]);via(net,escape)
  end=('C520','1')
  tree=r.paths_from(r.blocked(p.F_Cu,net),r.cell(r.xy(pads[end])),3)
  forbidden=set()
  for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden|=r.blocked(layer,net,.45,True)
  candidates=sorted((q for q in tree['distances'] if q not in forbidden),key=lambda q:tree['distances'][q]+((r.world(q)[0]-escape[0])**2+(r.world(q)[1]-escape[1])**2)**.5)
  found=False
  for q in candidates:
   path=r.solve(r.blocked(p.B_Cu,net),r.cell(escape),q)
   if not path:continue
   route(net,.2,[escape]+path+[r.world(q)],p.B_Cu);via(net,r.world(q))
   route(net,.2,[r.xy(pads[end])]+r.path_from_tree(tree,q))
   found=True;break
  assert found,'No bounded XIN bridge'
 else:
  end=('C521','1')
  r=LocalRouter(b,(52,27,64,39),width=.2,grid=.025)
  escape=(59.9,31.6);route(net,.15,[r.xy(pads[start]),escape])
  path=r.solve(r.blocked(p.F_Cu,net),r.cell(escape),r.cell(r.xy(pads[end])))
  assert path,'No front XOUT route'
  route(net,.2,[escape]+path+[r.xy(pads[end])])

out=D/'ethernet-clock-pins.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
from phy_clock_rules import PHY_CLOCK_NECK_RULE
rule=PHY_CLOCK_NECK_RULE
out.with_suffix('.kicad_dru').write_text(src.with_suffix('.kicad_dru').read_text()+rule)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'ethernet-clock-pins-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'ethernet-clock-grounds-drc.json').read_text()),json.loads((D/'ethernet-clock-pins-drc.json').read_text()));b.BuildConnectivity()

checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'ETHERNET_CLOCK_PINS_CONNECTED' if accepted else 'REJECTED_ETHERNET_CLOCK_PINS','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False,'replaced_copper':replaced,'limitations':['XIN uses two through vias; oscillator loading, noise coupling to L501 and frequency margin are not qualified.','The 5V detour preserves width, not a current or transient qualification.']}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b,replaced_copper=replaced)
(D/'ethernet-clock-pins.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
