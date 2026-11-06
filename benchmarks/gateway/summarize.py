#!/usr/bin/env python3
"""Read-only summary of the current integration run, no private credentials."""
import json,re
from pathlib import Path
root=Path('results/gatewaybench')
rows=[]
for line in (root/'server-final-exit.jsonl').read_text().splitlines():
 try:rows.append(json.loads(line))
 except json.JSONDecodeError:pass
samples=[r['result'] for r in rows if r.get('event')=='browser_result' and r['result'].get('test')=='endurance']
summary={'transfers':len(samples),'cycles':max((s['cycle'] for s in samples),default=0),'bytes':sum(s['bytes'] for s in samples)}
for d in ('download','upload'):
 a=[s for s in samples if s['direction']==d]
 if a:summary[d]={'mbps':sum(s['bytes'] for s in a)*8/sum(s['seconds'] for s in a)/1e6,'min':min(s['mbps'] for s in a),'max':max(s['mbps'] for s in a)}
summary['completion']=[r['result'] for r in rows if r.get('event')=='browser_result' and r['result'].get('test') in ('endurance_complete','endurance_error')]
log=(root/'uart-probe-fixed.log').read_text()
summary['latest_device_status']=next((s for s in reversed(log.splitlines()) if 'uplink=' in s),'')
summary['panics']=len(re.findall(r'Guru Meditation|panic\(|abort\(\)',log))
summary['boots']=log.count('ESP-ROM:')
print(json.dumps(summary,indent=2))
