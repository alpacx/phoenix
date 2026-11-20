#!/usr/bin/env python3
import pcbnew as p,json,os
from pathlib import Path
from pcb_preservation import verify_preservation
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel';source=p.LoadBoard(str(D/'lcd-dc.kicad_pcb'));out=D/'ground-vias.kicad_pcb';tests=[];held=[];old={t.m_Uuid.AsString() for t in source.GetTracks()}
def audit(b):
 proof=verify_preservation(source,b);new=[t for t in b.GetTracks() if t.m_Uuid.AsString() not in old];vs=[t for t in new if isinstance(t,p.PCB_VIA)]
 assert len(new)==10 and len(vs)==5
 assert all(t.GetNetname()=='GND' for t in new)
 assert all(v.GetWidth(p.F_Cu)==p.FromMM(.6) and v.GetDrillValue()==p.FromMM(.3) for v in vs)
 assert all(t.GetWidth()==p.FromMM(.3) for t in new if not isinstance(t,p.PCB_VIA))
 b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};group={q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['C435','2'])}
 for ref in ['C1670','C1659','C1653','C1648','C1660']:assert pads[ref,'2'].m_Uuid.AsString() in group
 return proof
def reject(name,b):
 try:audit(b)
 except AssertionError:tests.append({'test':name,'passed':True});return
 raise AssertionError('Negative accepted '+name)
audit(p.LoadBoard(str(out)));tests.append({'test':'accepted_ground_vias','passed':True})
reject('unrouted_source',p.LoadBoard(str(D/'lcd-dc.kicad_pcb')))
b=p.LoadBoard(str(out));t=next(t for t in b.GetTracks() if t.m_Uuid.AsString() not in old and not isinstance(t,p.PCB_VIA));t.SetWidth(p.FromMM(.15));reject('narrowed_signal',b)
b=p.LoadBoard(str(out));t=next(t for t in b.GetTracks() if t.m_Uuid.AsString() not in old and isinstance(t,p.PCB_VIA));t.SetDrill(p.FromMM(.1));reject('changed_via_drill',b)
b=p.LoadBoard(str(out));t=next(t for t in b.GetTracks() if t.m_Uuid.AsString() not in old and isinstance(t,p.PCB_VIA));b.Remove(t);held.append(t);reject('removed_via',b)
b=p.LoadBoard(str(out));t=next(t for t in b.GetTracks() if t.m_Uuid.AsString() in old);t.SetWidth(t.GetWidth()+p.FromMM(.01));reject('modified_existing_copper',b)
for ext in ['kicad_pro','kicad_dru']:assert (D/('lcd-dc.'+ext)).read_bytes()==(D/('ground-vias.'+ext)).read_bytes()
tests.append({'test':'unchanged_design_rules','passed':True})
(D/'ground-vias-tests.json').write_text(json.dumps({'tests':tests,'passed':len(tests)},indent=2)+'\n');print(json.dumps(tests),flush=True);os._exit(0)
