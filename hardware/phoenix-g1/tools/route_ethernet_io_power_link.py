#!/usr/bin/env python3
"""Join adjacent PHY 3.3 V digital supply pins; source and bypass still open."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs/pcb'
src=D/'ethernet-avdd33-bypass.kicad_pcb';proof=json.loads((D/'ethernet-avdd33-bypass.json').read_text());assert proof['status']=='ETHERNET_AVDD33_BYPASS_CONNECTED';assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['sha256']
b=p.LoadBoard(str(src));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  if a==z:continue
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
def via(net,xy):
 v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(v)
b.BuildConnectivity()
def xy(q):return (p.ToMM(q.GetPosition().x),p.ToMM(q.GetPosition().y))
route('+3V3_PHY',.2,[xy(pads['U5','28']),xy(pads['U5','29'])])

out=D/'ethernet-io-power-link.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'ethernet-io-power-link-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads((D/'ethernet-avdd33-bypass-drc.json').read_text()),json.loads((D/'ethernet-io-power-link-drc.json').read_text()));b.BuildConnectivity()
pairs=[(('U5','28'),('U5','29'))]
checks=[]
for a,z in pairs:checks.append({'from':'.'.join(a),'to':'.'.join(z),'connected':pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}})
accepted=not new and all(c['connected'] for c in checks)
r={'status':'ETHERNET_IO_POWER_LINK_CONNECTED' if accepted else 'REJECTED_ETHERNET_IO_POWER_LINK','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':proof['sha256'],'checks':checks,'new_violations':new,'assembly_ready':False}
if accepted:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b)
(D/'ethernet-io-power-link.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
