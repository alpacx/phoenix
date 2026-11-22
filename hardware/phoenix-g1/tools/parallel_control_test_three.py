#!/usr/bin/env python3
import pcbnew as p,json,os
from pathlib import Path
from parallel_control_audit import audit as base_audit
def audit(a,b):return base_audit(a,b,refs=("C1649","C1654","C1671","C1678","C1646"),expected_added=11)
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel';source=p.LoadBoard(str(D/'ground-returns-two.kicad_pcb'));out=D/'ground-returns-three.kicad_pcb';tests=[];held=[]
def reject(name,fn):
 try:fn()
 except AssertionError:tests.append({'test':name,'passed':True});return
 raise AssertionError('Negative test accepted '+name)
audit(source,p.LoadBoard(str(out)));tests.append({'test':'accepted_candidate','passed':True})
reject('unrouted_baseline',lambda:audit(source,p.LoadBoard(str(D/'ground-returns.kicad_pcb'))))
old={t.m_Uuid.AsString() for t in source.GetTracks()}
b=p.LoadBoard(str(out));new=next(t for t in b.GetTracks() if t.m_Uuid.AsString() not in old);new.SetWidth(p.FromMM(.2));reject('narrowed_return',lambda:audit(source,b))
b=p.LoadBoard(str(out));new=next(t for t in b.GetTracks() if t.m_Uuid.AsString() not in old);b.Remove(new);held.append(new);reject('removed_added_segment',lambda:audit(source,b))
b=p.LoadBoard(str(out));oldtrack=next(t for t in b.GetTracks() if t.m_Uuid.AsString() in old);oldtrack.SetWidth(oldtrack.GetWidth()+p.FromMM(.01));reject('modified_existing_copper',lambda:audit(source,b))
b=p.LoadBoard(str(out));f=next(f for f in b.GetFootprints() if f.GetReference()=='C466');q=f.GetPosition();f.SetPosition(p.VECTOR2I(q.x+p.FromMM(.1),q.y));reject('moved_existing_footprint',lambda:audit(source,b))
(D/'ground-returns-three-tests.json').write_text(json.dumps({'tests':tests,'passed':len(tests)},indent=2)+'\n');print(json.dumps(tests),flush=True);os._exit(0)
