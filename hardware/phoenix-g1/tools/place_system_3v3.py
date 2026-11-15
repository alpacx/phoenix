#!/usr/bin/env python3
"""System converter placement draft, retaining the existing Wi-Fi power-good enable."""
import pcbnew as p,json,hashlib,shutil,subprocess
from pathlib import Path
from pcb_preservation import verify_preservation
from drc_regression import introduced
E=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';S=E/'startup-power';D=E/'system-3v3/pcb';D.mkdir(parents=True,exist_ok=True)
cp=json.loads((S/'working-candidate.json').read_text());src=S/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()};held=[];replaced=[]
def vec(xy):return p.VECTOR2I(*(p.FromMM(v) for v in xy))
# Keep the original converter orientation and enable branch.
for ref,xy,angle,front in [('L1301',(14,36),270,True),('R1301',(18,30.5),0,True),('C1301',(16.5,32),0,False),('C1302',(15.3,30.2),0,False),('C1303',(16.5,28.5),0,False)]:
 f=fs[ref];assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads()),ref
 if (f.GetLayer()==p.F_Cu)!=front:f.Flip(f.GetPosition(),False)
 f.SetPosition(vec(xy));f.SetOrientationDegrees(angle)
def route(net,width,points,layer=p.F_Cu):
 for a,z in zip(points,points[1:]):
  t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
out=D/'placement.kicad_pcb'
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
shutil.copy2(src.parent/'fp-lib-table',D/'fp-lib-table')
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(D/'placement-drc.json'),str(out)],check=True,capture_output=True)
new=introduced(json.loads(src.with_name(src.stem+'-drc.json').read_text()),json.loads((D/'placement-drc.json').read_text()))
r={'status':'SYSTEM_PLACEMENT_ACCEPTED' if not new else 'REJECTED_SYSTEM_PLACEMENT','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':cp['sha256'],'replaced_copper':replaced,'new_violations':new,'assembly_ready':False}
if not new:r['preservation']=verify_preservation(p.LoadBoard(str(src)),b,replaced_copper=replaced)
(D/'placement.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
