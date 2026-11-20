#!/usr/bin/env python3
"""Check integrated netlist against all pin contracts and audit DC power paths.
This is a transcription/model check, not a power-integrity or hardware validation.
"""
import json,collections,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 x=ET.parse(ROOT/'review/integrated.xml');actual={};byref=collections.defaultdict(dict)
 for net in x.findall('.//nets/net'):
  for p in net.findall('node'):
   actual[p.get('ref'),p.get('pin')]=net.get('name');byref[p.get('ref')][p.get('pin')]=net.get('name')
 expected=json.loads((ROOT/'review/integrated-contract.json').read_text());errors=[]
 physical=[p for p in expected if not p['ref'].startswith('#')]
 for p in physical:
  a=actual.get((p['ref'],p['pin']));n=p['net']
  if (n is not None and a!=n) or (n is None and a and not a.startswith('unconnected-')):errors.append(dict(expected=p,actual=a))
 # Trace through only R/L. Capacitors and ICs are not treated as DC shorts.
 graph=collections.defaultdict(list)
 for ref,pins in byref.items():
  if ref.startswith(('R','L','FB')) and set(pins)=={'1','2'}:
   a,b=pins['1'],pins['2'];graph[a].append((b,ref));graph[b].append((a,ref))
 sources={'VBUS_RAW':'J1 USB source','GND':'J1 USB return'}
 for net in x.findall('.//nets/net'):
  for p in net.findall('node'):
   if p.get('pintype')=='power_out' and not p.get('ref','').startswith('#'):
    sources[net.get('name')]=p.get('ref')+'.'+p.get('pin')
 targets=['+3V58_WIFI','WIFI_VBAT','WIFI_BUCK_OUT','+1V0_PHY','+3V3_PHY','+3V3_SYS','VDD_CPU','VDD_CPU_COM','VDD_LOGIC','VDD_GPU','VDD_NPU','+1V5_DDR','USB_AVDD_0V9','USB_AVDD_1V8','VBUS_RAW','GND']
 paths={}
 for target in targets:
  queue=collections.deque([(target,[])]);seen=set()
  while queue:
   net,path=queue.popleft()
   if net in seen:continue
   seen.add(net)
   if net in sources:paths[target]={'source':sources[net],'source_net':net,'passive_path':path};break
   for nxt,ref in graph[net]:queue.append((nxt,path+[ref]))
  else:paths[target]={'error':'No DC path to documented source'}
 result={'status':'FAIL' if errors else 'PASS','checked_pin_dispositions':len(physical),'erc_annotations_not_in_physical_netlist':len(expected)-len(physical),'errors':errors,'power_paths':paths,'scope':'Net transcription and DC connectivity only. No current, sequencing, stability, signal integrity or thermal qualification.'}
 (ROOT/'review/integrated-connectivity.json').write_text(json.dumps(result,indent=2)+'\n')
 print(result['status'],len(physical),'pin dispositions;',len(errors),'differences')
 for n,p in paths.items():print(n,p)
 raise SystemExit(bool(errors))
if __name__=='__main__':main()
