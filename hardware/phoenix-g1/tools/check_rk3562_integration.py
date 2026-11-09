#!/usr/bin/env python3
"""Verify migration transcription without treating ERC warnings as approval."""
import json,re,collections,xml.etree.ElementTree as ET
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'migration-rk3562/review'
x=ET.parse(R/'integrated.xml');actual={}
for n in x.findall('.//nets/net'):
 for p in n.findall('node'):actual[p.get('ref'),p.get('pin')]=n.get('name')
expected=json.loads((R/'integrated-contract.json').read_text());diff=[]
for p in expected:
 a=actual.get((p['ref'],p['pin']));n=p['net']
 if (n is not None and a!=n) or (n is None and a and not a.startswith('unconnected-')):diff.append({'expected':p,'actual':a})
assert not any(ref=='R1405' for ref,pin in actual),'Legacy voltage strap still present'
categories=dict(collections.Counter(re.findall(r'^\[([^]]+)\]:',(R/'integrated-erc.txt').read_text(),re.M)))
report={'status':'FAIL' if diff else 'PASS TRANSCRIPTION ONLY','checked_pin_dispositions':len(expected),'differences':diff,'erc_categories':categories,'pending_soc_pins':sum(ref=='U1' and n.startswith('PENDING_') for (ref,pin),n in actual.items()),'production_ready':False}
(R/'integrated-connectivity.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert not diff
