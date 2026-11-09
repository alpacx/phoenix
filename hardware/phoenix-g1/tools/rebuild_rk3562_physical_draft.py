#!/usr/bin/env python3
"""Regenerate preliminary placement and partial USB controls; NOT full routing."""
import subprocess,sys,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];T=R/'tools';M=R/'migration-rk3562'
py='/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9';cli='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
for args in [['build_rk3562_floorplan.py'],['route_rk3562_usb_sense.py'],['route_rk3562_usb_sense.py','--controls'],['place_rk3562_usb_thresholds.py'],['route_rk3562_usb_sense.py','--auxiliary'],['route_rk3562_usb_sense.py','--power-sense'],['route_rk3562_usb_sense.py','--aon'],['route_rk3562_usb_sense.py','--returns']]:
 subprocess.run([py,str(T/args[0]),*args[1:]],check=True)
 if args==['build_rk3562_floorplan.py']:
  assembly=M/'review/floorplan-assembly-drc.json'
  subprocess.run([cli,'pcb','drc','--format','json','-o',str(assembly),str(M/'kicad/floorplan/phoenix-g1-floorplan.kicad_pcb')],check=True)
  errors=[a for a in json.loads(assembly.read_text())['violations'] if a['severity']=='error']
  assert not errors, 'Assembly placement DRC failed: '+str(errors)
 if args==['route_rk3562_usb_sense.py']:
  early=M/'review/pcb-early-drc.json'
  subprocess.run([cli,'pcb','drc','--format','json','-o',str(early),str(M/'kicad/pcb/phoenix-g1.kicad_pcb')],check=True)
  errors=[a for a in json.loads(early.read_text())['violations'] if a['severity']=='error']
  assert not errors, 'Early copper/placement DRC failed: '+str(errors)
subprocess.run([cli,'pcb','drc','--format','json','-o',str(M/'review/pcb-drc.json'),str(M/'kicad/pcb/phoenix-g1.kicad_pcb')],check=True)
subprocess.run([py,str(T/'check_rk3562_pcb.py')],check=True)
subprocess.run([py,str(T/'audit_rk3562_usb_returns.py'),'--require-ground','--require-source','--require-raw','--require-guard','--require-input','--require-bypass','--require-aon'],check=True)
subprocess.run([py,str(T/'audit_rk3562_courtyard_envelope.py'),'--require-enclosure'],check=True)
subprocess.run([sys.executable,str(T/'check_rk3562_release.py')],check=True)
print('Partial physical draft checked. Missing display footprint and all remaining routing/qualification are unresolved.')
