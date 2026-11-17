#!/usr/bin/env python3
"""Persist accepted corridor geometry; never updates authoritative PCB/BOM."""
from pathlib import Path
import json,hashlib,shutil,sys
S=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-compact-inductor'
if '--with-strap' in sys.argv:
 c=S/'corridor';cp=json.loads((c/'checkpoint.json').read_text());proof=json.loads((c/'rxclk-strap-probe.json').read_text());assert proof['status']=='RXCLK_STRAP_GEOMETRY_PASSED' and proof['parent_sha256']==cp['sha256']
 src=Path(proof['candidate']);assert hashlib.sha256(src.read_bytes()).hexdigest()==proof['candidate_sha256']
 d=c/'strap/pcb';d.mkdir(parents=True,exist_ok=True);out=d/'phoenix-phy-corridor.kicad_pcb';shutil.copy2(src,out)
 for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
 shutil.copy2(src.parent/'fp-lib-table',d/'fp-lib-table');shutil.copy2(src.parent/'drc.json',d/'drc.json')
 (c/'pre-strap-checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n');cp.update(board='strap/pcb/phoenix-phy-corridor.kicad_pcb',sha256=proof['candidate_sha256']);cp['source_reports']['rxclk-strap']=proof;cp['moves']['R522']=[*proof['R522_position_mm'],proof['R522_orientation_deg'],'B'];cp.pop('isolated_tests_passed',None)
 (c/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n');print('Corridor and RXCLK strap persisted; no production qualification.');raise SystemExit(0)
r=json.loads((S/'output-return-probe.json').read_text());assert r['status']=='OUTPUT_RETURN_GEOMETRY_PASSED';src=Path(r['candidate']);assert hashlib.sha256(src.read_bytes()).hexdigest()==r['candidate_sha256']
d=S/'corridor/pcb';d.mkdir(parents=True,exist_ok=True);out=d/'phoenix-phy-corridor.kicad_pcb'
shutil.copy2(src,out)
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(src.with_suffix(ext),out.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',d/'fp-lib-table');shutil.copy2(src.parent/'drc.json',d/'drc.json')
reports={n:json.loads((S/(n+'.json')).read_text()) for n in ['input-corridor-bypass','bulk-return-probe','output-return-probe']}
checkpoint={'status':'EXPERIMENTAL_PHY_POWER_CORRIDORS_NOT_ELECTRICALLY_QUALIFIED','board':'pcb/phoenix-phy-corridor.kicad_pcb','sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'base_study_sha256':reports['input-corridor-bypass']['parent_sha256'],'moves':reports['input-corridor-bypass']['moves'],'input_path_mm':reports['input-corridor-bypass']['input_path_mm'],'input_width_mm':1.05,'input_ground_width_mm':.5,'output_ground_width_mm':.5,'source_reports':reports,'authoritative_checkpoint_modified':False,'bom_selected':False,'assembly_ready':False,'limitations':['SW node, upstream 3.3V source and 1V load distribution remain open.','Existing narrow pin/bypass fanout is not qualified for main supply current.','New RX termination positions require layer/fanout/timing verification.','No ripple, impedance, stability, thermal or physical qualification.']}
(S/'corridor/checkpoint.json').write_text(json.dumps(checkpoint,indent=2)+'\n');print('Corridor geometry persisted; no production qualification.')
