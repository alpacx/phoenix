#!/usr/bin/env python3
import json,collections,hashlib
from pathlib import Path
import pcbnew as p
R=Path(__file__).resolve().parents[1];D=R/'migration-rk3562/experiments/stacked-expansion/pcb';a=p.LoadBoard(str(D/'candidate.kicad_pcb'));b=p.LoadBoard(str(D/'control-routed.kicad_pcb'))
def tracks(board):
 return {t.m_Uuid.AsString():(t.GetNetname(),t.GetLayer(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth()) for t in board.GetTracks()}
x,y=tracks(a),tracks(b);assert all(y.get(k)==v for k,v in x.items())
old=json.loads((D/'drc.json').read_text());new=json.loads((D/'control-drc.json').read_text());count=lambda d:collections.Counter(v['type'] for v in d['violations']);assert count(old)==count(new)
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};b.BuildConnectivity();report=json.loads((D/'control-routed.json').read_text())
for r in report['routes']:
 if not r['routed']:continue
 start,end=[pads[tuple(s.split('.'))] for s in r['endpoints']];assert end.m_Uuid.AsString() in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(start)}
report.update(status='LOCAL_CONTINUITY_AND_DRC_CHECKED_NOT_POWER_QUALIFIED',old_copper_preserved=len(x),new_track_segments=len(y)-len(x),drc_categories=dict(count(new)),holds=['GPIO local pull resistors routed; links to SoC and J3 not routed','Ground returns and complete power path not routed','dVdt shortened to 2.83mm; noise immunity not qualified by continuity','USB differential pair not routed','Mechanical reserves not cleared'])
(D/'control-routed.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
