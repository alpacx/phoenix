#!/usr/bin/env python3
"""Test all exact-DRC placements obstructed solely by the same GND segment."""
import hashlib,json,subprocess,sys
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
cp=json.loads((D/'working-candidate.json').read_text());src=D/cp['board']
pre=json.loads((D/'pcb/phy-bulk-exact-clearance-probe.json').read_text())
assert pre['source_sha256']==cp['sha256']==hashlib.sha256(src.read_bytes()).hexdigest()
capids={'480b132d-2229-4892-912a-28300a78afb5','dc3c5c3d-cb72-4cb1-925c-07e1e19bceb0'}
trials=[]
for t in pre['trials']:
 obstacles={uid for v in t['new_violations'] if v['type'] not in ['track_dangling','unconnected_items'] for uid in v['items']}-capids
 if obstacles != {'545b053b-db69-41f9-bd1f-f3135bcf88b9'}:continue
 c=t['placement']
 cmd=[sys.executable,str(Path(__file__).with_name('probe_phy_output_bulk_ground.py')),'--with-input-bulk','--capacitor-position',*(str(v) for v in c['center_mm']),'--capacitor-angle',str(c['angle_deg'])]
 subprocess.run(cmd,check=True,capture_output=True,timeout=120)
 r=json.loads((D/'pcb/phy-combined-bulk-ground-probe.json').read_text());trials.append(r)
 print(c,r['status'],flush=True)
 if r['status']=='LOCAL_GROUND_TRIAL_PASSED':break
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
(D/'pcb/phy-bulk-detour-matrix.json').write_text(json.dumps({'source_sha256':cp['sha256'],'trials':trials,'checkpoint_modified':False,'assembly_ready':False},indent=2)+'\n')
