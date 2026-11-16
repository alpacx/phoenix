#!/usr/bin/env python3
"""Connect the display buffer supply to the display regulator output. Geometry/continuity only."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'display-buffer-bypass.kicad_pcb';proof=json.loads((D/'display-buffer-bypass.json').read_text());assert proof['status']=='DISPLAY_BUFFER_BYPASS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
from local_pcb_router import LocalRouter
r=LocalRouter(b,(19,20,30,37),width=.3,grid=.025);r.max_expansions=200000
start=r.xy(pads['C1811','1']);goal=r.xy(pads['C1802','1'])
path=r.solve(r.blocked(p.F_Cu,'+3V0_LCD'),r.cell(start),r.cell(goal))
assert path,'No front route'
route('+3V0_LCD',.3,[start]+path+[goal])
out=D/'display-buffer-feed.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'display-buffer-feed-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'display-buffer-bypass-drc.json').read_text()),json.loads((D/'display-buffer-feed-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('U21','20'),('U20','5'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'DISPLAY_BUFFER_FEED_CONNECTED' if accepted else 'REJECTED_DISPLAY_BUFFER_FEED','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'display-buffer-feed.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
