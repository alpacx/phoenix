#!/usr/bin/env python3
"""Rotate J3 in an isolated branch before rebuilding its connections."""
import pcbnew as p,json,shutil,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';S=R/'stacked-expansion/pcb';D=R/'stacked-expansion-rotated/pcb';D.mkdir(parents=True,exist_ok=True);b=p.LoadBoard(str(S/'input-feed.kicad_pcb'));b.BuildConnectivity();f=next(f for f in b.GetFootprints() if f.GetReference()=='J3')
assert not any(b.GetConnectivity().GetConnectedTracks(a) for a in f.Pads())
refpos=f.Reference().GetPosition();refangle=f.Reference().GetTextAngle();f.SetOrientationDegrees(f.GetOrientationDegrees()+180);f.Reference().SetPosition(refpos);f.Reference().SetTextAngle(refangle)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(D/'input-feed.kicad_pcb'),b)
for name in ['candidate.kicad_pcb','candidate.kicad_pro','candidate.kicad_dru','drc.json','logic-reference-drc.json']:shutil.copy2(S/name,D/name)
for ext in ['kicad_dru','kicad_pro']:shutil.copy2(S/f'input-feed.{ext}',D/f'input-feed.{ext}')
(D/'fp-lib-table').write_text((S/'fp-lib-table').read_text().replace('${KIPRJMOD}/../system','${KIPRJMOD}/../../stacked-expansion/system'))
(D.parent/'study.json').write_text(json.dumps({'status':'ISOLATED_ROTATION_STUDY_NOT_PROMOTED','rotation_degrees':180,'connector_center_mm':[67.5,2.5],'pinout_changed':False,'all_J3_pads_unrouted_before_rotation':True,'source_sha256':hashlib.sha256((S/'input-feed.kicad_pcb').read_bytes()).hexdigest(),'assembly_ready':False},indent=2)+'\n')
