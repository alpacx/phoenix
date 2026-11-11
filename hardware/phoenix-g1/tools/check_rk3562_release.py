#!/usr/bin/env python3
"""Record release blockers without treating geometric DRC as board completion."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1]/'migration-rk3562';V=R/'review'
read=lambda name:json.loads((V/(name+'.json')).read_text())
pcb=read('pcb-connectivity-check');state=read('completion-status');returns=read('usb-return-audit')
courtyards=read('courtyard-envelope-audit');wifi=read('wifi-converter-copper-audit')
actual=hashlib.sha256((R/'kicad/pcb/phoenix-g1.kicad_pcb').read_bytes()).hexdigest()
assert pcb['pcb_sha256']==actual and returns['pcb_sha256']==actual and courtyards['pcb_sha256']==actual and wifi['pcb_sha256']==actual,'Stale verification evidence'
checks={
 'courtyard_pad_enclosure':not courtyards['findings'],
 'geometric_drc':not pcb['geometric_drc_violations'],
 'pad_net_transcription':not pcb['net_mismatches'],
 'usb_18_signal_nets':all(a['connected'] for a in pcb['usb_copper_continuity']),
 'usb_local_ground_escapes':all(a['has_copper_escape'] for a in returns['ground_returns']),
 'usb_source_ground_continuity':all(a['connected_to_usb_source_ground'] for a in returns['ground_returns']),
 'usb_bypass_continuity':all(a['all_target_pins_connected'] for a in returns['bypass_placement']),
 'usb_vbus_source_to_guard':returns['usb_vbus_source_to_guard']['connected'],
 'usb_aon_supply':returns['usb_aon_supply']['connected'],
 'usb_guard_to_main':returns['usb_guard_to_main']['connected'],
 'usb_input_power_chain':all(a['connected'] for a in returns['usb_input_power_chain']),
 'wifi_converter_local_nets':wifi['local_nets_complete'],
 'wifi_converter_direct_front_ground':wifi['agnd_pgnd_and_power_caps_direct_front_to_ep'],
 'wifi_converter_front_power':all(a['connected_on_front'] for a in wifi['front_power_connections']),
 'usb_main_switch_to_wifi_converter':wifi['usb_main_switch_to_wifi_converter'],
 'wifi_power_good_to_system_enable':wifi['power_good_to_system_enable'],
 'wifi_converter_source_ground':wifi['local_grounds_continuous_to_usb_source'],
 'wifi_output_to_ferrite':wifi['output_to_ferrite'],
 'wifi_ferrite_to_module_and_bypass':wifi['ferrite_to_module_and_bypass'],
 'wifi_module_bypass_ground':wifi['module_bypass_ground_to_usb'],
 'wifi_all_module_grounds':not wifi['unconnected_module_ground_pads'],
 'wifi_module_buck_switch':wifi['module_buck_switch_connected'],
 'wifi_module_buck_output':wifi['module_buck_output_connected'],
 'wifi_module_buck_cap_ground':wifi['module_buck_cap_ground_to_usb'],
 'wifi_module_buck_switch_back_only':wifi['module_buck_switch_back_only_no_vias'],
 'wifi_vddio_local_bypass':wifi['vddio_local_bypass_connected'],
 'wifi_vddio_bypass_ground':wifi['vddio_bypass_ground_to_usb'],
 'wifi_vddio_upstream_pmic':wifi['vddio_upstream_pmic_connected'],
 'wifi_lpo_source_signal':wifi['lpo_source_to_series_resistor'],
 'wifi_lpo_module_signal':wifi['lpo_series_resistor_to_module'],
 'wifi_lpo_source_ground':wifi['lpo_source_ground_to_usb'],
 'wifi_lpo_source_power':wifi['lpo_source_power_from_pmic'],
 'all_board_connections':pcb['unconnected_ratsnest_edges']==0,
 'all_physical_pads_present':not pcb['missing_physical_pads'],
 'all_soc_pin_decisions':state['pending_pins']==0,
}
report={'status':'BLOCKED FOR FABRICATION','pcb_sha256':actual,'checks':checks,
 'unverified_required_items':['RK3562 DDR3 RZQ/VREF connection and timing/layout prescriptions','RK3562 supply sequence and PMIC defaults','FCCSP478 lands, stencil and escape process','Power distribution, bypass loop impedance and current/temperature margins','Display attachment and footprint','High-speed routing and SI/PI','Passive enclosure thermal/mechanical qualification','Via filling/plugging and stencil process; assembly quotation'],
 'required_external_input':'RK3562-specific manufacturer design/layout/package documents or written supplier confirmation. See manufacturer-information-request.txt.',
 'unconnected_ratsnest_edges':pcb['unconnected_ratsnest_edges'],'production_ready':False,'gerbers_released':False}
(V/'release-gate.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
