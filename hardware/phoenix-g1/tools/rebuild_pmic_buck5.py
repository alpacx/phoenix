#!/usr/bin/env python3
"""Transactional BUCK5 geometry/connectivity rebuild; not electrical qualification."""
import os,sys,json,shutil,tempfile,subprocess
from pathlib import Path
T=Path(__file__).resolve().parent;D=T.parent/'migration-rk3562/experiments/pmic-buck5'
steps=[
('place_pmic_buck5.py',{}),('rework_addon_bus_for_pmic.py',{}),
('route_pmic_buck5_switch.py',{}),
('route_pmic_buck5_ground.py',{'GROUND_REFS':'C425'}),
('place_pmic_output_front.py',{}),
('route_pmic_buck5_output.py',{'PRIMARY_OUTPUT_ONLY':'1'}),
('route_pmic_buck5_ground.py',{'GROUND_SOURCE':'output','GROUND_STAGE':'output-ground','GROUND_REFS':'C425,C435'}),
('reroute_pmic_io_escape.py',{}),('prepare_pmic_input_first.py',{}),
('route_pmic_buck5_input.py',{'INPUT_SOURCE':'input-first'}),
('route_pmic_buck5_switch.py',{'SWITCH_SOURCE':'input','SWITCH_STAGE':'switch-reclosed'}),
('route_pmic_buck5_feedback.py',{'FEEDBACK_SOURCE':'switch-reclosed','FEEDBACK_STAGE':'feedback-reclosed'}),
('place_pmic_second_output.py',{}),
('route_pmic_buck5_ground.py',{'GROUND_SOURCE':'second-output','GROUND_STAGE':'second-ground'}),
('route_pmic_buck5_output.py',{'OUTPUT_SOURCE':'second-ground','OUTPUT_STAGE':'local-complete'}),
('audit_pmic_buck5.py',{'IO_REWORK':'1','AUDIT_STAGE':'local-complete'}),
('check_pmic_buck5_connections.py',{}),('clear_pmic_mounts.py',{}),
('audit_pmic_buck5.py',{'IO_REWORK':'1','AUDIT_STAGE':'mount-local-trial'}),
('check_pmic_buck5_connections.py',{'CONNECTION_STAGE':'mount-local-trial'}),
('place_pmic_mount_bypasses.py',{}),
('route_pmic_buck5_ground.py',{'GROUND_SOURCE':'mount-bypasses','GROUND_STAGE':'mount-bypasses-ground','GROUND_REFS':'C422,C470'}),
('add_daughterboard_mount_holes.py',{}),('route_pmic_io_bypass.py',{}),
('audit_pmic_buck5.py',{'IO_REWORK':'1','AUDIT_STAGE':'io-bypass'}),
('check_pmic_buck5_connections.py',{'CONNECTION_STAGE':'io-bypass'}),
('tidy_dense_silkscreen.py',{}),
('audit_pmic_buck5.py',{'IO_REWORK':'1','AUDIT_STAGE':'layout-reviewed'}),
('check_pmic_buck5_connections.py',{'CONNECTION_STAGE':'layout-reviewed'})]
with tempfile.TemporaryDirectory(prefix='phoenix-buck5-') as tmp:
 backup=Path(tmp)/'pcb';shutil.copytree(D/'pcb',backup);pointers=[D/'study-checkpoint.json',D/'working-candidate.json'];old={p:p.read_bytes() if p.exists() else None for p in pointers}
 try:
  for script,settings in steps:
   env={k:v for k,v in os.environ.items() if not k.startswith('PHOENIX_BUCK5_')};env.update({'PHOENIX_BUCK5_'+k:v for k,v in settings.items()});print('Running',script,settings,flush=True)
   result=subprocess.run([sys.executable,str(T/script)],env=env,capture_output=True,text=True)
   if result.returncode:raise RuntimeError(script+'\n'+result.stdout[-3000:]+'\n'+result.stderr[-3000:])
  report=json.loads((D/'pcb/local-complete-preservation-audit.json').read_text());assert not report['new_drc_violations']
  mounts=json.loads((D/'pcb/mount-local-trial.json').read_text());assert not mounts['new_individual_violations']
  cp=json.loads((D/'study-checkpoint.json').read_text());cp.update(promoted_to_main=True,schematic='../emmc-system/system/kicad/integrated/phoenix-g1.kicad_sch');(D/'working-candidate.json').write_text(json.dumps(cp,indent=2)+'\n')
  subprocess.run([sys.executable,str(T/'inventory_stacked_connectivity.py'),'--checkpoint',str(D/'working-candidate.json')],check=True)
  print('BUCK5 rebuild passed; local topology only, manufacturing and power qualification remain open.',flush=True)
 except BaseException:
  shutil.rmtree(D/'pcb');shutil.copytree(backup,D/'pcb')
  for pointer,data in old.items():
   if data is None:pointer.unlink(missing_ok=True)
   else:pointer.write_bytes(data)
  print('Restored previous PCB directory and checkpoint.',flush=True);raise
