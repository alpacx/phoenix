#!/usr/bin/env python3
"""Negative copper fixture: a broken LPO clock path must fail the independent audit."""
import argparse,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
import pcbnew as p
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--board',type=Path,required=True);ap.add_argument('--report',type=Path,required=True)
a=ap.parse_args();tool=Path(__file__).with_name('audit_rk3562_wifi_converter.py')
with tempfile.TemporaryDirectory(prefix='phoenix-lpo-negative-') as tmp:
 tmp=Path(tmp);board=p.LoadBoard(str(a.board));removed=[]
 for t in list(board.GetTracks()):
  if t.GetNetname()=='WIFI_LPO' and t.GetClass()=='PCB_TRACK' and t.GetLayer()==p.In2_Cu:removed.append(t);board.Remove(t)
 assert removed,'Fixture requires an already routed LPO net'
 p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(tmp/'broken.kicad_pcb'),board)
 result=subprocess.run([sys.executable,str(tool),'--board',str(tmp/'broken.kicad_pcb'),'--report',str(tmp/'audit.json'),'--require-local','--require-module-supply','--require-module-ground','--require-module-buck','--require-lpo'],capture_output=True,text=True)
 evidence=json.loads((tmp/'audit.json').read_text())
 assert result.returncode!=0 and 'Clock resistor-to-module disconnected' in result.stderr
 assert not evidence['lpo_series_resistor_to_module']
 assert evidence['lpo_source_to_series_resistor'] and evidence['lpo_source_ground_to_usb']
 assert evidence['module_buck_switch_connected']
 assert evidence['module_buck_output_connected'] and evidence['module_buck_cap_ground_to_usb']
 assert evidence['local_nets_complete'] and evidence['ferrite_to_module_and_bypass']
 assert not evidence['unconnected_module_ground_pads']
 report={'status':'PASS: DISCONNECTED LPO PATH DETECTED','source_pcb_sha256':hashlib.sha256(a.board.read_bytes()).hexdigest(),'removed_lpo_inner_tracks':len(removed),'expected_failure':'Clock resistor-to-module disconnected','other_module_supply_and_ground_checks_passed':True,'simulation_performed':False,'physical_test_performed':False}
 a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
