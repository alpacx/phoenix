#!/usr/bin/env python3
"""Integrated fault injection: cut/narrow/wrong-net/additional hole."""
import pcbnew as p,json,sys,subprocess,os
from pathlib import Path
from parallel_local_copper_checks import validate,D as DELTA
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
if len(sys.argv)>1:
 case=sys.argv[1];b=p.LoadBoard(str(D/'pcb/parallel-local-copper.kicad_pcb'));d=json.loads((DELTA/'delta.json').read_text());uids={q['uuid'] for q in d['tracks']};t=next(t for t in b.GetTracks() if t.m_Uuid.AsString() in uids);held=[]
 if case=='cut':b.Remove(t);held.append(t)
 elif case=='narrow':t.SetWidth(p.FromMM(.2))
 elif case=='wrongnet':t.SetNetCode(b.GetNetcodeFromNetname('+3V3_IO'))
 elif case=='wronglayer':t.SetLayer(p.In1_Cu)
 elif case=='same_net_pad_overlap':
  f=next(f for f in b.GetFootprints() if f.GetReference()=='C1106');q=next(q for q in f.Pads() if q.GetNumber()=='2');assert q.GetNetname()=='GND';q.SetPosition(p.VECTOR2I(p.FromMM(23.3),p.FromMM(20.6)))
 elif case=='hole':next(f for f in b.GetFootprints() if f.GetReference()=='H8105').SetPosition(p.VECTOR2I(p.FromMM(70.5),p.FromMM(34)))
 try:validate(b);ok=case=='accepted'
 except (AssertionError,KeyError):ok=case!='accepted'
 print(case,ok,flush=True);os._exit(0 if ok else 1)
rows=[]
for case in ['accepted','cut','narrow','wrongnet','wronglayer','hole','same_net_pad_overlap']:
 r=subprocess.run([sys.executable,__file__,case],capture_output=True,text=True);rows.append({'case':case,'passed':r.returncode==0})
(D/'pcb/parallel-local-copper-tests.json').write_text(json.dumps({'tests':rows,'all_passed':all(r['passed'] for r in rows)},indent=2)+'\n');print(rows);assert all(r['passed'] for r in rows)
