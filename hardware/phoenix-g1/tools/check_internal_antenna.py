#!/usr/bin/env python3
"""Check exported candidate nets and mutually exclusive assembly selectors."""
from pathlib import Path
import json,xml.etree.ElementTree as E
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/internal-antenna'
x=E.parse(r/'review/netlist.xml').getroot()
nets={n.attrib['name'].lstrip('/'):{(p.attrib['ref'],p.attrib['pin']) for p in n.findall('node')} for n in x.findall('./nets/net')}
expected={'WIFI_RF':{('R2001','1'),('R2005','1')},'WIFI_INT_MATCH':{('R2005','2'),('R2006','1'),('C2010','1')},'WIFI_INT_ANT':{('R2006','2'),('L2002','1'),('AE2001','1')},'WIFI_ANT':{('R2001','2')},'GND':{('L2002','2'),('C2010','2')}}
for net,pins in expected.items():assert nets[net]==pins,(net,nets.get(net))
assert not any(('AE2001','2') in pins for net,pins in nets.items() if not net.startswith('unconnected-'))
components={c.attrib['ref']:c for c in x.findall('./components/comp')}
dnp={ref for ref,c in components.items() if any(p.attrib.get('name')=='dnp' for p in c.findall('property'))}
assert dnp=={'C2010','R2001'},dnp
j={'status':'PASS_CANDIDATE_TOPOLOGY','checked_nets':len(expected),'dnp':sorted(dnp),'pcb_integrated':False,'rf_qualified':False}
(r/'review/topology-check.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j))
