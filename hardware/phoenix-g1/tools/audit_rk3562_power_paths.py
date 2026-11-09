#!/usr/bin/env python3
"""DC topology only. Does not equate a path with correct voltage or power sequencing."""
from pathlib import Path
import collections,json,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1]/'migration-rk3562/review'
x=ET.parse(R/'integrated.xml'); byref=collections.defaultdict(dict);types={};sources={};targets=set()
values={c.get('ref'):c.findtext('value','') for c in x.findall('.//components/comp')}
for n in x.findall('.//nets/net'):
 name=n.get('name')
 for p in n.findall('node'):
  ref=p.get('ref');pin=p.get('pin');kind=p.get('pintype');byref[ref][pin]=name
  if kind=='power_out':sources[name]=ref+'.'+pin
  if kind=='power_in':targets.add(name)
# USB input and return are external sources; they are not self-powered PCB rails.
sources.update({'VBUS_RAW':'J1 external USB supply, conditional on source capability','GND':'J1 return'})
graph=collections.defaultdict(list);edges=[]
for ref,pins in byref.items():
 if set(pins)!={'1','2'}:continue
 value=values.get(ref,'')
 allowed=ref.startswith(('L','FB')) or (ref.startswith('R') and value.split()[0] in ('0R','0','0Ω','0ohm'))
 if not allowed:continue
 a,b=pins['1'],pins['2'];graph[a].append((b,ref));graph[b].append((a,ref));edges.append({'ref':ref,'value':value,'nets':[a,b]})
paths=[]
for target in sorted(targets):
 q=collections.deque([(target,[])]);seen=set();found=None
 while q:
  n,path=q.popleft()
  if n in seen:continue
  seen.add(n)
  if n in sources:found={'source_net':n,'source':sources[n],'series_components':path};break
  q.extend((nextnet,path+[ref]) for nextnet,ref in graph[n])
 paths.append({'rail':target,'path':found,'result':'TOPOLOGY_PATH_FOUND' if found else 'NO_PATH'})
report={'status':'DC TOPOLOGY SCREEN ONLY','rails':paths,'allowed_series_edges':edges,'missing_paths':[p['rail'] for p in paths if not p['path']],'limits':['Switch nodes count as conditional sources through output inductors; regulation and default voltage are not validated.','No assumptions about high-value resistors, capacitors, MOSFET channels or unpowered IC pass-through.','Current capacity, inductive transients, input headroom, enable logic and sequencing require separate review.','No PWR_FLAG or ERC suppression added.']}
(R/'power-path-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(len(paths),'power nets;',report['missing_paths'],'without DC path')
