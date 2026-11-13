#!/usr/bin/env python3
"""Rebuild routing stages sequentially; stop on tool failure or new DRC violations."""
import subprocess, pathlib,shutil,json,collections
root=pathlib.Path(__file__).resolve().parents[3];py='/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3';cli='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli';T=root/'hardware/phoenix-g1/tools';D=root/'hardware/phoenix-g1/migration-rk3562/experiments/stacked-expansion/pcb'
def run(name,args=[]):
 r=subprocess.run([py,str(T/name)]+args,capture_output=True,text=True);print(name,r.returncode,flush=True)
 if r.returncode:print(r.stdout,r.stderr);raise SystemExit(r.returncode)
def drc(board,report):
 r=subprocess.run([cli,'pcb','drc','--format','json','-o',str(D/report),str(D/board)],capture_output=True,text=True);print(r.stdout.strip(),flush=True);r.check_returncode()
 baseline=collections.Counter(v['type'] for v in json.loads((D/'drc.json').read_text())['violations']);counts=collections.Counter(v['type'] for v in json.loads((D/report).read_text())['violations'])
 if board=='output-bus.kicad_pcb':baseline['via_dangling']+=1
 assert all(v<=baseline[k] for k,v in counts.items()),('New DRC errors',board,dict(counts))
run('protect_stacked_mounts.py');drc('mount-protected.kicad_pcb','mount-protected-drc.json')
run('route_stacked_control.py');drc('control-routed.kicad_pcb','control-drc.json')
run('route_stacked_ground.py',['--input',str(D/'control-routed.kicad_pcb'),'--output',str(D/'ground-routed.kicad_pcb'),'--report',str(D/'ground-routed.json')]);drc('ground-routed.kicad_pcb','ground-drc.json')
for script,stem in [('route_stacked_local_power.py','local-power'),('route_stacked_fault_supply.py','fault-supply'),('route_stacked_input_feed.py','input-feed'),('route_stacked_output_bus.py','output-bus'),('route_stacked_output_feed.py','output-feed')]:run(script);drc(stem+'.kicad_pcb',stem+'-drc.json')
run('route_stacked_connector_ground.py',['--input',str(D/'output-feed.kicad_pcb'),'--output',str(D/'connector-ground.kicad_pcb'),'--report',str(D/'connector-ground.json')]);drc('connector-ground.kicad_pcb','connector-ground-drc.json')
run('route_stacked_connector_controls.py');drc('connector-controls.kicad_pcb','connector-controls-drc.json')

run('route_stacked_soc_controls.py');drc('soc-controls.kicad_pcb','soc-controls-drc.json')
run('route_stacked_logic_reference.py');drc('logic-reference.kicad_pcb','logic-reference-drc.json')
run('audit_stacked_local_power.py',['logic-reference'])

audit=json.loads((D/'logic-reference-audit.json').read_text())
required=['input_feed_connected','output_J3_connected','GPIO_to_SoC_connected','fault_pullup_supply_connected','J3_ground_connected','J3_logic_reference_connected']
assert all(audit[k] for k in required),audit
assert len(audit['mechanical_copper_reservations_enforced'])==5
(D.parent/'working-candidate.json').write_text(json.dumps({'status':'POWER_CONTROLS_ROUTED_WITH_MECHANICAL_RESERVATIONS','board':'pcb/logic-reference.kicad_pcb','sha256':audit['sha256'],'verification':'pcb/logic-reference-audit.json','assembly_ready':False},indent=2)+'\n')
