#!/usr/bin/env python3
"""System buck local power copper, explicitly not current/thermal qualification."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';S=E/'system-3v3';D=E/'pmic-ldo-inputs/pcb';D.mkdir(parents=True,exist_ok=True)
proof=json.loads((D/'vcc9-link.json').read_text());src=D/'vcc9-link.kicad_pcb';assert proof['status']=='PMIC_VCC9_GROUP_JOINED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.8));v.SetDrill(p.FromMM(.4));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
# Draft distribution; copper/via current and voltage drop remain unqualified.
b.BuildConnectivity();f=next(f for f in b.GetFootprints() if f.GetReference()=='TP4')
assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads())
f.SetPosition(vec((55.5,38.5)))
via('+3V3_SYS',(18.55,38.75))
via('+3V3_SYS',(18.55,36.65))
route('+3V3_SYS',.8,[(18.55,36.65),(18.55,37.3)],p.In4_Cu)
via('+3V3_SYS',(55.5,38.5))
route('+3V3_SYS',.8,[(18.55,38.75),(18.55,37.3),(22.5,37.3),(24.35,39.15),(49,39.15),(49,37),(52.5,37)],p.In4_Cu)
route('+3V3_SYS',.8,[(52.5,37),(51.8,36.3),(51.8,34.8),(53.7,32.9),(53.7,27),(52.5,25.8),(52.5,11.5),(54,11.5)],p.In4_Cu)
route('+3V3_SYS',.8,[(49,39.15),(54.85,39.15),(55.5,38.5)],p.In4_Cu)
out=D/'system-feed.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'system-feed-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'system-feed-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('C1304','1'),('C480','1')),(('C1304','1'),('TP4','1'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'SYSTEM_SOURCE_TO_PMIC_CONNECTED' if accepted else 'REJECTED_SYSTEM_FEED','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False,'manufacturing_requirement':'C1304/C1305 via-in-pad must be filled and capped; current capability and final stackup unqualified'}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'system-feed.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
