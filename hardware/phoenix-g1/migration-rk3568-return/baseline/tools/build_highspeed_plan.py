#!/usr/bin/env python3
"""Bind reviewed Rockchip routing requirements to actual schematic paths.
This is a constraint manifest, not a routed-board or SI pass report.
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
x=ET.parse(ROOT/'review/integrated.xml')
nets={n.get('name'):[{'ref':v.get('ref'),'pin':v.get('pin')} for v in n.findall('node')] for n in x.findall('.//nets/net')}
components={c.get('ref'):c for c in x.findall('.//components/comp')}
def has(net,ref,pin=None):
 return any(n['ref']==ref and (pin is None or n['pin']==str(pin)) for n in nets[net])
def link(a,b,ref):
 assert has(a,ref) and has(b,ref),(a,b,ref)
 assert len({n['pin'] for name in (a,b) for n in nets[name] if n['ref']==ref})==2,ref
 return {'component':ref,'value':components[ref].findtext('value')}
rgmii=[]
for direction,signals,start in [('TX',['TXD0','TXD1','TXD2','TXD3','TXEN','TXCLK'],501),('RX',['RXD0','RXD1','RXD2','RXD3','RXDV_CRS','RXCLK'],507)]:
 for i,signal in enumerate(signals):
  a,b='ETH_'+signal,'PHY_'+signal;ref=f'R{start+i}'
  resistor=link(a,b,ref)
  assert has(a,'U1') and has(b,'U5')
  assert resistor['value'].split()[0]=='22R'
  rgmii.append({'signal':signal,'group':direction,'net_segments':[a,b],'series':resistor,'source_ref':'U1' if direction=='TX' else 'U5','receiver_ref':'U5' if direction=='TX' else 'U1','match_reference':direction+'CLK','branches':[n for n in nets[a]+nets[b] if n['ref'] not in ['U1','U5',ref]],'source_termination_placement':'Place 22R near source; RX source is U5, TX source is U1.'})
usb=[]
for direction in ['TX','RX']:
 for orientation in [1,2]:
  polarities={}
  for pol in ['P','N']:
   soc=f'SOC_USB_{direction}_{pol}';connector=f'USB_{direction}{orientation}_{pol}'
   assert has(soc,'U1') and has(soc,'U6') and has(connector,'J1')
   segments=[soc];series=[]
   if direction=='TX':
    mux=f'MUX_TX{orientation}_{pol}';cap=f'C{600+2*(orientation-1)+(1 if pol=="P" else 2)}'
    coupling=link(mux,connector,cap)
    assert coupling['value'].split()[0]=='100n'
    assert has(mux,'U6')
    series.append(coupling);segments.append(mux)
   else:assert has(connector,'U6')
   segments.append(connector)
   polarities[pol]={'net_segments':segments,'series':series}
  usb.append({'path':f'{direction}_orientation_{orientation}','polarities':polarities,'switch':'U6','note':'Alternative orientations are mutually exclusive; include switch/package delay in SI. Do not sum both branches as one active path.'})
report={
 'status':'ROUTING CONSTRAINT PLAN ONLY - NOT IMPLEMENTED OR MEASURED',
 'source':{'file':'reference/Rockchip_RK3568_High_Speed_PCB_Design_Guide_V10_EN_2021-4-12.pdf','revision':'V1.0, 2021-04-12','visually_reviewed_pages':[13,22]},
 'rules':{
  'usb3':{'differential_impedance_ohm':90,'tolerance_percent':10,'intra_pair_mismatch_mm_strictly_less_than':0.3048,'trace_length_mm_strictly_less_than':152.4,'recommended_max_vias':2,'pair_to_pair_clearance_multiple_of_width_min':4,'other_signal_clearance_multiple_of_width_min':4,'coupling_capacitance_nf':100,'coupling_tolerance_percent_max':20,'preferred_cap_package':'0201; existing 0402 must be assessed for discontinuity'},
  'rgmii':{'single_ended_impedance_ohm':50,'tolerance_percent':10,'data_control_to_group_clock_mismatch_mm_strictly_less_than':3.048,'trace_length_mm_strictly_less_than':127,'within_group_clearance_multiple_of_width_min':2,'other_signal_clearance_multiple_of_width_min':2,'other_signal_clearance_multiple_of_width_recommended':3}},
 'usb3_paths':usb,'rgmii_paths':rgmii,
 'net_endpoints':{name:nets[name] for name in sorted({s for p in rgmii for s in p['net_segments']}|{s for p in usb for lane in p['polarities'].values() for s in lane['net_segments']})},
 'verification':{'schematic_paths':'PASS connectivity assertions','routed_lengths':'NOT CHECKED','impedance':'NOT CALCULATED','timing':'NOT SIMULATED'},
 'holds':['Do not apply full-path length limits independently to each net segment.','PCB dielectric stackup and copper thickness must determine widths and pair gaps; none are invented here.','Vias, return path discontinuities, ESD branches, switch and package delay require SI review.','Copper-length matching is insufficient if segments use layers with different propagation speeds.','DDR and Ethernet MDI constraints are not covered by this manifest.','RGMII PHY and MAC delay configuration must agree with timing model.','No production release or completed placement follows from these assertions.']}
(ROOT/'review/highspeed-routing-plan.json').write_text(json.dumps(report,indent=2)+'\n')
print('Bound',len(usb),'USB3 orientation paths and',len(rgmii),'RGMII paths to',len(report['net_endpoints']),'schematic nets')
