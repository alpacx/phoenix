#!/usr/bin/env python3
"""Regression and intentional-fault checks for the isolated PHY geometry."""
import json,os,subprocess,sys,hashlib
from pathlib import Path
import pcbnew as p
from pcb_route_guards import require_constant_width_branch
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
variant=os.environ.get('PHOENIX_PHY_TEST_VARIANT','joint-002')
assert variant in ['joint-002','joint-16v']
R=D/'runs'/variant/'report.json'
if len(sys.argv)==1:
 cases=['nominal','narrow_switch','narrow_output','cut_neck','cut_output','qualification_hold']
 results=[]
 for case in cases:
  r=subprocess.run([sys.executable,__file__,case],capture_output=True,text=True)
  results.append({'case':case,'passed':r.returncode==0,'output':r.stdout.strip(),'stderr':r.stderr.strip()})
 (D/('tests.json' if variant=='joint-002' else 'tests-16v.json')).write_text(json.dumps(results,indent=2)+'\n')
 print(json.dumps(results,indent=2));sys.exit(0 if all(x['passed'] for x in results) else 1)
m=json.loads(R.read_text());path=Path(m['candidate']);assert hashlib.sha256(path.read_bytes()).hexdigest()==m['candidate_sha256'];b=p.LoadBoard(str(path));tracks={t.m_Uuid.AsString():t for t in b.GetTracks()};routes={r['label']:r for r in m['routes']};case=sys.argv[1];held=[]
def guard(label):
 r=routes[label];return require_constant_width_branch([tracks[u] for u in r['uuids']],net=r['net'],layer=p.F_Cu if r['layer']=='F.Cu' else p.B_Cu,width_mm=r['width_mm'],start_mm=r['path_mm'][0],end_mm=r['path_mm'][-1])
def connected(a,z):
 b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};return pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}
if case=='nominal':
 assert not m['new_violations'] and not m['new_mechanical_conflicts']
 for label in routes:guard(label)
 assert all(c['connected'] for c in m['checks']);assert connected(('U5','30'),('L501','1'))
elif case.startswith('narrow_'):
 label='switch_trunk' if case=='narrow_switch' else 'output';tracks[routes[label]['uuids'][0]].SetWidth(p.FromMM(1.5));caught=False
 try:guard(label)
 except (ValueError,AssertionError):caught=True
 assert caught,'Width reduction was not detected'
elif case.startswith('cut_'):
 label='pin_fanout' if case=='cut_neck' else 'output'
 for uid in routes[label]['uuids']:
  t=tracks[uid];b.Remove(t);held.append(t)
 assert not connected(('U5','30'),('L501','1')) if case=='cut_neck' else not connected(('L501','2'),('C511','1'))
else:
 assert m['status']=='JOINT_SW_GEOMETRY_PASSED_PIN_FANOUT_HOLD'
 assert not m['power_layout_accepted'] and not m['assembly_ready'] and not m['historical_60mil_width_met_on_entire_path']
 assert routes['pin_fanout']['width_mm']<1.524
print(case+': PASS',flush=True);os._exit(0)
