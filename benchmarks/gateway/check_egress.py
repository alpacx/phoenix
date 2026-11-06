#!/usr/bin/env python3
"""Local orchestration; requires monitor_control.py and Mac capture already active."""
import json,time,struct
from pathlib import Path
root=Path('results/gatewaybench');command=root/'uart-command.txt';log=root/'uart-probe-fixed.log'
def send(s):
 temp=command.with_suffix('.tmp');temp.write_text(f'{time.time_ns()} bench {s}\n');temp.replace(command);time.sleep(1)
def mode(s):
 offset=len(log.read_text());send(s)
 if 'MODE '+s not in log.read_text()[offset:]:raise RuntimeError('No mode acknowledgment: '+s)
 if s=='vpn':
  deadline=time.monotonic()+20
  while 'vpn=1 direct=0' not in log.read_text()[offset:]:
   if time.monotonic()>deadline:raise RuntimeError('No fresh VPN handshake')
   time.sleep(.2)
phases=[]
try:
 deadline=time.monotonic()+35
 while 'vpn=1' not in log.read_text():
  if time.monotonic()>deadline:raise RuntimeError('No initial handshake')
  time.sleep(1)
 for state in ('vpn','blocked','direct','blocked'):
  mode(state)
  start=time.time();offset=len(log.read_text());send('probe');time.sleep(2);end=time.time()
  if 'probe injected: 3 UDP' not in log.read_text()[offset:]:raise RuntimeError('No probe completion acknowledgment')
  phases.append({'mode':state,'start':start,'end':end})
finally:
 mode('vpn')
(root/'egress-phases.json').write_text(json.dumps(phases,indent=2)+'\n')
# Only classify the uniquely marked synthetic packets visible on this Mac.
data=(root/'egress-wide.pcap').read_bytes();off=24
endian='<' if data[:4]==b'\xd4\xc3\xb2\xa1' else '>'
counts=[[] for _ in phases]
while off+16<=len(data):
 sec,usec,n,_=struct.unpack_from(endian+'IIII',data,off);off+=16
 if off+n>len(data):break
 b=data[off:off+n];off+=n
 if len(b)<42 or b[12:14]!=b'\x08\x00' or b[23]!=17:continue
 ident=int.from_bytes(b[18:20],'big')
 if ident not in (64000,64001,64002):continue
 if b[30:34]!=bytes((192,168,8,103)):continue
 stamp=sec+usec/1e6
 for i,p in enumerate(phases):
  if p['start']<=stamp<=p['end']:counts[i].append({'id':ident,'port':int.from_bytes(b[36:38],'big')})
for p,c in zip(phases,counts):
 p['plaintext_packets']=c;p['pass']=(len(c)==3 if p['mode']=='direct' else len(c)==0)
(root/'egress-results.json').write_text(json.dumps(phases,indent=2)+'\n')
print(json.dumps(phases,indent=2))
if not all(p['pass'] for p in phases):raise SystemExit('Egress check failed or inconclusive')
