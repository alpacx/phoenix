#!/usr/bin/env python3
"""Resolve conservative C511 screening with real KiCad DRC; no power routing."""
import hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
import pcbnew as p
from drc_regression import introduced
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
cp=json.loads((D/'working-candidate.json').read_text());src=D/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
pre=json.loads((D/'pcb/phy-bulk-placement-probe.json').read_text());assert pre['source_sha256']==cp['sha256']
candidates=next(c for c in pre['capacitors'] if c['reference']=='C511')['conservative_copper_rejections']
base=json.loads(src.with_name(src.stem+'-drc.json').read_text())
original=p.LoadBoard(str(src));key=lambda row:(row['reservation'],row['ref'])
oldconf={key(row) for row in screen(original)}
outdir=Path(tempfile.mkdtemp(prefix='phoenix-bulk-exact-'));out=outdir/src.name
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
(outdir/'fp-lib-table').write_text((src.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}',str(src.parent)))
trials=[];accepted=None
for index,c in enumerate(candidates):
 b=p.LoadBoard(str(src));f=next(f for f in b.GetFootprints() if f.GetReference()=='C511')
 f.SetPosition(p.VECTOR2I(*(p.FromMM(x) for x in c['center_mm'])));f.SetOrientationDegrees(c['angle_deg'])
 conflicts=sorted({key(row) for row in screen(b)}-oldconf)
 if conflicts:continue
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 drc=outdir/'drc.json'
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(out)],check=True,capture_output=True)
 new=introduced(base,json.loads(drc.read_text()))
 geometry=[v for v in new if v['type'] not in ['track_dangling','unconnected_items']]
 trials.append({'placement':c,'new_violations':new,'geometry_acceptable':not geometry})
 print(index+1,len(candidates),'geometry',not geometry,flush=True)
 if not geometry:
  accepted=c;break
result={'status':'EXACT_PLACEMENT_FOUND_GROUND_AND_POWER_OPEN' if accepted else 'NO_EXACT_PLACEMENT_IN_TESTED_SET',
 'source_sha256':cp['sha256'],'trials':trials,'accepted_geometry':accepted,'temporary_candidate':str(out) if accepted else None,
 'checkpoint_modified':False,'assembly_ready':False,
 'limitations':['Only candidates rejected by the conservative copper screen are tested.',
 'Unconnected items and dangling old ground branches are excluded ONLY from placement acceptance; continuity must be restored and full DRC rerun before promotion.',
 'No power copper, current capacity, loop impedance or stability qualification.']}
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
(D/'pcb/phy-bulk-exact-clearance-probe.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],flush=True)
