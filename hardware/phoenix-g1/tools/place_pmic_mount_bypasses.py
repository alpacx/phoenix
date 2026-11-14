#!/usr/bin/env python3
"""Move two unrouted bypasses near PMIC and away from daughterboard reservations."""
import pcbnew as p,json,subprocess,shutil,hashlib
from pathlib import Path
from drc_regression import introduced
from pcb_preservation import verify_preservation
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-buck5';src=D/'pcb/mount-local-trial.kicad_pcb';cp={'sha256':hashlib.sha256(src.read_bytes()).hexdigest()};assert cp['sha256']==json.loads((D/'pcb/mount-local-trial-preservation-audit.json').read_text())['sha256'];O=D/'pcb';out=O/'mount-bypasses.kicad_pcb';b=p.LoadBoard(str(src));b.BuildConnectivity();base=json.loads(src.with_name(src.stem+'-drc.json').read_text());records=[]
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
for ref,positions in [('C422',[(54,10.5),(54,11),(54,9.5)]),('C470',[(63,6.5),(64,6.5),(62.5,7.5),(64,7.5),(61,7.5)])]:
 f=next(f for f in b.GetFootprints() if f.GetReference()==ref);assert not any(b.GetConnectivity().GetConnectedTracks(a) for a in f.Pads());old=f.GetPosition();side=f.GetLayer();angle=f.GetOrientationDegrees();trials=[];accepted=False
 if side!=p.B_Cu:f.Flip(old,False)
 f.SetOrientationDegrees(0 if ref=='C470' else 180)
 for x,y in positions:
  f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(O/'mount-bypasses-drc.json'),str(out)],check=True,capture_output=True);new=introduced(base,json.loads((O/'mount-bypasses-drc.json').read_text()));trials.append({'position':[x,y],'new_violations':new});print(ref,x,y,len(new),flush=True)
  if not new:accepted=True;break
 if not accepted:
  if f.GetLayer()!=side:f.Flip(f.GetPosition(),False)
  f.SetPosition(old);f.SetOrientationDegrees(angle)
 records.append({'ref':ref,'accepted':accepted,'trials':trials})
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(O/'mount-bypasses-drc.json'),str(out)],check=True,capture_output=True)
report={'source_sha256':cp['sha256'],'moves':records,'preservation':verify_preservation(p.LoadBoard(str(src)),b),'new_violations':introduced(base,json.loads((O/'mount-bypasses-drc.json').read_text())),'electrical_placement_qualified':False,'assembly_ready':False};(O/'mount-bypasses.json').write_text(json.dumps(report,indent=2)+'\n')
