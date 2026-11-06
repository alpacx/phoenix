#!/usr/bin/env python3
"""Exercise real board admin APIs through the loopback-only lab bridge.
Temporarily installs rules for synthetic client .250 only, then restores policy.
"""
import copy,json,time,urllib.request,urllib.error
from pathlib import Path
BASE='http://127.0.0.1:8085/api/v1/'
def request(path,body=None,headers=None):
 data=None if body is None else json.dumps(body).encode()
 req=urllib.request.Request(BASE+path,data=data,headers={'Content-Type':'application/json',**(headers or {})})
 try:
  with urllib.request.urlopen(req,timeout=15) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
code,old=request('policy');assert code==200
Path('results/gatewaybench/admin-policy-backup.json').write_text(json.dumps(old,indent=2))
try:
 p=copy.deepcopy(old)
 p['rules'].append(dict(name='QA synthetic client only',enabled=True,allow=False,ingress='ap',protocol=0,source='192.168.9.250/32',destination='0.0.0.0/0',port_first=0,port_last=0))
 p['forwards'].append(dict(name='QA restricted mapping',enabled=True,vpn=True,protocol=17,external_port=18081,internal_port=8081,target='192.168.9.250/32',source='10.77.0.1/32'))
 code,saved=request('policy',p);assert code==200,(code,saved)
 assert saved['revision']==old['revision']+1 and saved['rules'][-1]['name']==p['rules'][-1]['name']
 assert saved['forwards'][-1]['active'] is True
 print('PASS: policy committed, revision incremented, restricted VPN port mapping installed')
 code,_=request('policy',p);assert code==409
 print('PASS: stale revision rejected')
 invalid=copy.deepcopy(saved);invalid['forwards'][-1]['external_port']=51820
 code,_=request('policy',invalid);assert code==400
 invalid=copy.deepcopy(saved);invalid['rules'][-1]['source']='256.0.0.0/24'
 code,_=request('policy',invalid);assert code==400
 code,unchanged=request('policy');assert unchanged==saved
 print('PASS: invalid CIDR and reserved WireGuard port rejected without altering live policy')
 code,_=request('vpn',dict(action='nordvpn',country='XX',rotation=True,interval=30));assert code==400
 code,_=request('vpn',dict(action='nordvpn',country='IT',rotation=True,interval=0));assert code==400
 code,_=request('vpn',dict(action='wireguard',profile='PrivateKey=invalid'));assert code==400
 print('PASS: malformed VPN profile, unsupported country and invalid interval rejected')
 code,state=request('status');assert code==200 and state['vpn_up'] and not state['direct']
 print('PASS: existing encrypted Internet path remains active during configuration tests')
finally:
 _,current=request('policy');old['revision']=current['revision'];code,restored=request('policy',old);assert code==200,(code,restored)
 print('RESTORED: original policy; no test port left open')
