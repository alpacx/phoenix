#!/usr/bin/env python3
"""Audit exported connectivity; not power, timing, footprint or boot qualification."""
import json,xml.etree.ElementTree as ET,hashlib,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments';D=R/'emmc-system';V=D/'system/review'
x=ET.parse(V/'integrated.xml');nets={n.get('name'):{(a.get('ref'),a.get('pin')) for a in n.findall('node')} for n in x.findall('.//nets/net')};pins={pin:net for net,ps in nets.items() for pin in ps}
contract=json.loads((V/'integrated-contract.json').read_text())
for r in contract:
 actual=pins.get((r['ref'],r['pin']))
 assert actual==r['net'] if r['net'] is not None else actual is None or actual.startswith('unconnected-'),(r,actual)
changes=json.loads((D/'integration.json').read_text())
for c in changes['soc_pin_changes']:assert pins['U1',c['ball']]==c['to'],c
for m in json.loads((R/'emmc-8gb/signal-map.json').read_text()):
 net=m['signal'];assert any(ref=='U8001' for ref,pin in nets[net]),net
assert {('U1','M25'),('R8004','1')}<=nets['SOC_EMMC_CLK']
assert {('R8004','2'),('U8001','M6')}<=nets['EMMC_CLK']
assert pins['U1','1G15']=='+3V3_IO'
assert pins['C8010','1']==pins['U1','1F14']=='EMMC_IO_1V8' and pins['C8010','2']=='GND'
assert pins['R8005','1']=='EMMC_STRB' and pins['R8005','2']=='GND'
assert nets['EMMC_VDDI']=={('C8001','1'),('U8001','C2')}
refs={c.get('ref') for c in x.findall('.//components/comp')}
assert not refs.intersection(changes['removed_boot_flash_references'])
assert 'U8001' in refs
# Compare every existing pin against source; only explicit migrations/removals allowed.
old=ET.parse(V/'source-stacked.xml');oldpins={(a.get('ref'),a.get('pin')):n.get('name') for n in old.findall('.//nets/net') for a in n.findall('node')};allowed={('U1',c['ball']) for c in changes['soc_pin_changes']};checked=0
for k,v in oldpins.items():
 if k[0] in changes['removed_boot_flash_references'] or k in allowed or v.startswith('unconnected-'):continue
 assert pins.get(k)==v,(k,v,pins.get(k));checked+=1
counts=collections.Counter(v['type'] for sh in json.loads((V/'integrated-erc.json').read_text())['sheets'] for v in sh.get('violations',[]))
assert not counts['lib_symbol_issues'] and not counts['footprint_link_issues'],counts
report={'status':'EXPORTED_NETLIST_CHECKED_POWER_AND_PCB_OPEN','netlist_sha256':hashlib.sha256((V/'integrated.xml').read_bytes()).hexdigest(),'contract_dispositions_checked':len(contract),'soc_changes_verified':len(allowed),'other_connected_pins_preserved':checked,'old_NOR_removed':True,'VCCIO3_preserved':True,'VDDI_internal_only':True,'erc_categories':dict(counts),'power_sources_qualified':False,'PCB_updated':False,'boot_tested':False,'assembly_ready':False};(V/'migration-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
