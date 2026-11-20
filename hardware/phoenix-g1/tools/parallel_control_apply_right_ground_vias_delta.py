#!/usr/bin/env python3
"""Apply tested LCD_DC additions; caller runs integrated fill, DRC and preservation."""
import pcbnew as p,json
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel'
def apply(board,delta_path=D/'right-ground-vias-delta.json'):
 d=json.loads(Path(delta_path).read_text());existing={t.m_Uuid.AsString() for t in board.GetTracks()}
 assert not any(q['uuid'] in existing for q in d['tracks']), 'Ground via delta already/partially applied'
 for q in d['tracks']:
  assert q['net']=='GND'
  if q['via']:
   assert q['width_mm']==.6 and q['drill_mm']==.3
   t=p.PCB_VIA(board);t.SetPosition(p.VECTOR2I(*(p.FromMM(v) for v in q['start_mm'])));t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetViaType(p.VIATYPE_THROUGH);t.SetDrill(p.FromMM(q['drill_mm']))
  else:
   assert q['width_mm']==.3
   t=p.PCB_TRACK(board);t.SetLayer(board.GetLayerID(q['layer']));t.SetStart(p.VECTOR2I(*(p.FromMM(v) for v in q['start_mm'])));t.SetEnd(p.VECTOR2I(*(p.FromMM(v) for v in q['end_mm'])))
  t.SetUuid(p.KIID(q['uuid']));t.SetWidth(p.FromMM(q['width_mm']));t.SetNetCode(board.GetNetcodeFromNetname(q['net']));board.Add(t)
 board.BuildConnectivity();pads={f.GetReference()+'.'+a.GetNumber():a for f in board.GetFootprints() for a in f.Pads()}
 for q in d['checks']:assert pads[q['to']].m_Uuid.AsString() in {v.m_Uuid.AsString() for v in board.GetConnectivity().GetConnectedItems(pads[q['from']])}, q
 return {'added_copper':len(d['tracks']),'verified_pairs':d['checks'],'requires_integrated_drc':True,'assembly_ready':False}
