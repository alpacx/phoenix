#!/usr/bin/env python3
"""Rebuild isolated J3 rotation study, stopping on new DRC categories/counts."""
import subprocess,os,json,collections
from pathlib import Path
T=Path(__file__).resolve().parent;R=T.parent;D=R/'migration-rk3562/experiments/stacked-expansion-rotated/pcb';N='/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3';C='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli';env=dict(os.environ,PHOENIX_STACKED_PCB_DIR=str(D),PHOENIX_VIA_DIAMETER='.45',PHOENIX_VIA_DRILL='.2')
def run(*args):subprocess.run([str(a) for a in args],env=env,check=True)
def check(stage,extra_via=0):
 run(C,'pcb','drc','--format','json','-o',D/(stage+'-drc.json'),D/(stage+'.kicad_pcb'))
 counts=lambda p:collections.Counter(v['type'] for v in json.loads(p.read_text())['violations']);allowed=counts(D/'drc.json');allowed['via_dangling']+=extra_via;new=counts(D/(stage+'-drc.json'))-allowed
 assert not new,(stage,dict(new));print('DRC PASS '+stage,flush=True)
run(N,T/'study_stacked_rotation.py');check('input-feed')
for script,stage in [('route_stacked_output_bus.py','output-bus'),('route_stacked_output_feed.py','output-feed')]:run(N,T/script);check(stage,1 if stage=='output-bus' else 0)
run(N,T/'route_stacked_connector_ground.py','--input',D/'output-feed.kicad_pcb','--output',D/'connector-ground.kicad_pcb','--report',D/'connector-ground.json')
check('connector-ground')
for script,stage in [('route_stacked_connector_controls.py','connector-controls'),('route_stacked_soc_controls.py','soc-controls'),('route_stacked_logic_reference.py','logic-reference')]:run(N,T/script);check(stage)
run(N,T/'audit_stacked_local_power.py','logic-reference')
print('ROTATION STUDY FUNCTIONAL CONNECTION AUDIT PASSED; NOT PROMOTED',flush=True)
