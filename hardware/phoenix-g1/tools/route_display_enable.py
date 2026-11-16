#!/usr/bin/env python3
"""Connect the display regulator enable input. Geometry/continuity only."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'display-led-feed.kicad_pcb';proof=json.loads((D/'display-led-feed.json').read_text());assert proof['status']=='DISPLAY_LED_FEED_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
from local_pcb_router import LocalRouter
import math
r=LocalRouter(b,(20,2,70,38),width=.2,grid=.05)
plan=json.loads((D/'display-enable-path.json').read_text())
blocked=r.blocked(plan['layer'],'+3V3_IO')
def clear(a,z):
 n=max(1,math.ceil(math.dist(a,z)/.01))
 return all(r.cell((a[0]+(z[0]-a[0])*i/n,a[1]+(z[1]-a[1])*i/n)) not in blocked for i in range(n+1))
path=plan['path'];simple=[path[0]];i=0
while i<len(path)-1:
 j=len(path)-1
 while j>i+1 and not clear(path[i],path[j]):j-=1
 simple.append(path[j]);i=j
route('+3V3_IO',.2,plan['front'])
via('+3V3_IO',plan['via'])
route('+3V3_IO',.2,simple,plan['layer'])
out=D/'display-enable.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'display-enable-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'display-led-feed-drc.json').read_text()),json.loads((D/'display-enable-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('U20','3'),('U4','55'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'DISPLAY_ENABLE_CONNECTED' if accepted else 'REJECTED_DISPLAY_ENABLE','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'display-enable.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
