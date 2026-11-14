"""Negative checks: copper, pad-net and physical-connectivity regressions must fail."""
import unittest
import pcbnew as p
from pcb_preservation import verify_preservation

class PreservationTests(unittest.TestCase):
 def board(self):
  b=p.BOARD();net=p.NETINFO_ITEM(b,'TEST');b.Add(net)
  for ref,x in [('J1',1),('J2',3)]:
   f=p.FOOTPRINT(b);f.SetReference(ref);b.Add(f);q=p.PAD(f);q.SetNumber('1');q.SetSize(p.VECTOR2I(500000,500000));q.SetPosition(p.VECTOR2I(x*1000000,1000000));q.SetNetCode(net.GetNetCode());layers=p.base_seqVect();layers.append(p.F_Cu);q.SetLayerSet(p.LSET(layers));q.SetAttribute(p.PAD_ATTRIB_SMD);f.Add(q)
  t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(1000000,1000000));t.SetEnd(p.VECTOR2I(3000000,1000000));t.SetLayer(p.F_Cu);t.SetWidth(200000);t.SetNetCode(net.GetNetCode());b.Add(t)
  return b
 def copies(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory() as d:
   path=str(Path(d)/'test.kicad_pcb');b=self.board();p.SaveBoard(path,b);return p.LoadBoard(path),p.LoadBoard(path)
 def test_unchanged(self):
  a,b=self.copies();self.assertEqual(verify_preservation(a,b)['existing_tracks_vias_preserved'],1)
 def test_changed_copper(self):
  a,b=self.copies();next(iter(b.GetTracks())).SetWidth(300000)
  with self.assertRaises(AssertionError):verify_preservation(a,b)
 def test_changed_pad_net(self):
  a,b=self.copies();next(iter(next(iter(b.GetFootprints())).Pads())).SetNetCode(0)
  with self.assertRaises(AssertionError):verify_preservation(a,b)
 def test_moved_connected_pad(self):
  a,b=self.copies();next(iter(next(iter(b.GetFootprints())).Pads())).SetPosition(p.VECTOR2I(9000000,9000000))
  with self.assertRaises(AssertionError):verify_preservation(a,b)
if __name__=='__main__':unittest.main()
