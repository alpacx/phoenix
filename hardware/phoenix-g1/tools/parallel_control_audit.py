#!/usr/bin/env python3
"""Audit added ground returns without weakening board rules."""
import pcbnew as p
from pcb_preservation import verify_preservation
REFS=('C466','C468','C469','C465','C467','C463','C464')
def audit(source,board,refs=REFS,expected_added=13):
 proof=verify_preservation(source,board)
 old={t.m_Uuid.AsString() for t in source.GetTracks()}
 added=[t for t in board.GetTracks() if t.m_Uuid.AsString() not in old]
 assert len(added)==expected_added, 'Unexpected copper delta'
 assert all(not isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND' and t.GetWidth()==p.FromMM(.3) for t in added), 'Ground geometry or width changed'
 sf={f.m_Uuid.AsString():f for f in source.GetFootprints()};bf={f.m_Uuid.AsString():f for f in board.GetFootprints()}
 assert sf.keys()==bf.keys()
 for uid,a in sf.items():
  z=bf[uid];assert a.GetPosition()==z.GetPosition() and a.GetOrientationDegrees()==z.GetOrientationDegrees() and a.GetLayer()==z.GetLayer(), 'Footprint placement changed'
 board.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in board.GetFootprints() for q in f.Pads()}
 target=pads['C435','2'].m_Uuid.AsString()
 for ref in refs:assert target in {q.m_Uuid.AsString() for q in board.GetConnectivity().GetConnectedItems(pads[ref,'2'])}, 'Missing ground return '+ref
 return proof
