#!/usr/bin/env python3
"""Apply isolated tested GND additions to an integrating board; caller runs final DRC."""
import pcbnew as p,json
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel'
def apply(board,delta_path=D/'delta.json'):
 d=json.loads(Path(delta_path).read_text());existing={t.m_Uuid.AsString() for t in board.GetTracks()}
 assert not any(q['uuid'] in existing for q in d['tracks']), 'Delta already present or partially applied'
 for q in d['tracks']:
  assert q['net']=='GND' and q['width_mm']==.3 and q['layer'] in ('F.Cu','B.Cu')
  t=p.PCB_TRACK(board);t.SetUuid(p.KIID(q['uuid']));t.SetNetCode(board.GetNetcodeFromNetname(q['net']));t.SetLayer(board.GetLayerID(q['layer']));t.SetWidth(p.FromMM(q['width_mm']));t.SetStart(p.VECTOR2I(*(p.FromMM(v) for v in q['start_mm'])));t.SetEnd(p.VECTOR2I(*(p.FromMM(v) for v in q['end_mm'])));board.Add(t)
 board.BuildConnectivity();pads={f.GetReference()+'.'+a.GetNumber():a for f in board.GetFootprints() for a in f.Pads()}
 for q in d['checks']:assert pads[q['to']].m_Uuid.AsString() in {v.m_Uuid.AsString() for v in board.GetConnectivity().GetConnectedItems(pads[q['from']])}, q
 return {'added_tracks':len(d['tracks']),'verified_pairs':d['checks'],'requires_integrated_drc':True,'assembly_ready':False}
