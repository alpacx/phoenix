#!/usr/bin/env python3
"""Independent pin/rail checks against manufacturer inventory and exported netlist."""
from pathlib import Path
import csv,json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
x=ET.parse(ROOT/'review/integrated.xml');actual={}
for net in x.findall('.//nets/net'):
 for node in net.findall('node'):actual[node.get('ref'),node.get('pin')]=net.get('name')
rows={r['ball']:r for r in csv.DictReader((ROOT/'review/rk3568-manufacturer-pins.csv').open())}
a=json.loads((ROOT/'review/expansion-pinout.json').read_text());checks=[]
for s in a['soc_signals']:
 r=rows[s['ball']];f=s['function'];assert f in r['name'].split('/') or f in r['functions'].split(' | '),(f,r)
 assert actual['U1',s['ball']]==actual['J3',str(s['pin'])]==s['net'],s
 assert r['power_domain'] in ['PMUIO2','VCCIO4','VCCIO6'],r
 checks.append(dict(s,power_domain=r['power_domain']))
for pin,net in a['pinout'].items():assert actual['J3',pin]==net,(pin,net)
assert len({s['ball'] for s in checks})==13
result={'status':'PASS PIN ALLOCATION AND NET TRANSCRIPTION ONLY','signals':checks,'connector_pins_checked':20,'holds':a['qualification_holds'],'limitation':'No electrical loading, rise-time, power budget, mechanical fit or functional validation.'}
(ROOT/'review/expansion-check.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
