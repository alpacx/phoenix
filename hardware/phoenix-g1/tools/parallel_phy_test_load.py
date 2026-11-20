#!/usr/bin/env python3
import json,os,sys,subprocess,hashlib
from pathlib import Path
import pcbnew as p
from pcb_route_guards import require_constant_width_branch
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';variant=os.environ.get('PHOENIX_PHY_LOAD_VARIANT','load-in3-north2');assert variant in ['load-in3-north2','load-in3-c514c','load-in3-c513d','load-c513-16v'];R=D/'runs'/variant/'report.json';target='C513' if variant in ['load-in3-c513d','load-c513-16v'] else 'C514' if variant=='load-in3-c514c' else 'C512'
if len(sys.argv)==1:
 out=[]
 for case in ['nominal','narrow_track','cut_source_array','cut_load_array','ground_plane_roles','qualification_hold']:
  r=subprocess.run([sys.executable,__file__,case],capture_output=True,text=True);out.append({'case':case,'passed':r.returncode==0,'output':r.stdout.strip(),'stderr':r.stderr.strip()})
 (D/('tests-c513-16v.json' if variant=='load-c513-16v' else 'tests-c513.json' if target=='C513' else 'tests-c514.json' if target in ['C513','C514'] else 'tests-load.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2));sys.exit(0 if all(x['passed'] for x in out) else 1)
m=json.loads(R.read_text());path=Path(m['candidate']);assert hashlib.sha256(path.read_bytes()).hexdigest()==m['candidate_sha256'];b=p.LoadBoard(str(path));tracks={t.m_Uuid.AsString():t for t in b.GetTracks()};route=m['routes'][0];case=sys.argv[1];held=[]
def connected():
 b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};return pads[target,'1'].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['C511','1'])}
def guard():return require_constant_width_branch([tracks[u] for u in route['uuids']],net='+1V0_PHY',layer=p.In3_Cu,width_mm=1.55,start_mm=route['path_mm'][0],end_mm=route['path_mm'][-1])
if case=='nominal':
 assert not m['new_violations'] and connected();assert all(x['connected'] for x in m['checks']);guard();assert len(m['via_array'])==(2 if target in ['C513','C514'] else 4)
 for v in m['via_array']:
  t=tracks[v['uuid']];assert t.GetWidth(p.F_Cu)==p.FromMM(.6) and t.GetDrillValue()==p.FromMM(.3)
elif case=='narrow_track':
 tracks[route['uuids'][0]].SetWidth(p.FromMM(1.5));caught=False
 try:guard()
 except (ValueError,AssertionError):caught=True
 assert caught
elif case.startswith('cut_'):
 for v in ([{'uuid':u} for u in route['uuids']] if target in ['C513','C514'] and case=='cut_source_array' else m['via_array'] if target in ['C513','C514'] else m['via_array'][:2] if case=='cut_source_array' else m['via_array'][2:]):
  t=tracks[v['uuid']];b.Remove(t);held.append(t)
 assert not connected()
elif case=='ground_plane_roles':
 for u in route['uuids']:assert tracks[u].GetLayer()==p.In3_Cu
 assert all(z.GetNetname()=='GND' for z in b.Zones() if z.GetLayer() in [p.In1_Cu,p.In4_Cu] and not z.GetIsRuleArea())
else:assert not m['current_via_PI_qualified'] and not m['via_pad_overlap_manufacturing_qualified'] and not m['power_layout_accepted'] and not m['assembly_ready']
print(case+': PASS',flush=True);os._exit(0)
