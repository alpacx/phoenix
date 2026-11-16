#!/usr/bin/env python3
"""Connect Connect PHY crystal pins with scoped 0.15 mm pad necks and 0.2 mm front traces."""
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
b.BuildConnectivity()
from local_pcb_router import LocalRouter
pairs=[(('U5','36'),('Y501','1')),(('U5','37'),('Y501','3'))]
for start,check_end in pairs:
 end=('C521','1') if start==('U5','37') else check_end
 net=pads[start].GetNetname();r=LocalRouter(b,(53,28,62,36),width=.2,grid=.025)
 source=r.xy(pads[start]);escape=(59.8,source[1])
 route(net,.15,[source,escape])
 if start==('U5','37'):
  route(net,.2,[escape,(59.6,31.6),(59.6,33.5)]);escape=(59.6,33.5)
 path=r.solve(r.blocked(p.F_Cu,net),r.cell(escape),r.cell(r.xy(pads[end])))
 assert path,('clock route blocked',start,end)
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
r={'status':'ETHERNET_CLOCK_PINS_CONNECTED' if accepted else 'REJECTED_ETHERNET_CLOCK_PINS','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'ethernet-clock-pins.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
