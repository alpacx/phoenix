import unittest
import pcbnew as p
from local_pcb_router import smd_copper_layer
class SmdLayerTests(unittest.TestCase):
 def pad(self,layers):
  self.board=p.BOARD();self.fp=p.FOOTPRINT(self.board);self.board.Add(self.fp);pad=p.PAD(self.fp);self.fp.Add(pad);seq=p.base_seqVect()
  for layer in layers:seq.append(layer)
  pad.SetLayerSet(p.LSET(seq));return pad
 def test_front(self):self.assertEqual(smd_copper_layer(self.pad([p.F_Cu])),p.F_Cu)
 def test_back_uses_layer_set(self):self.assertEqual(smd_copper_layer(self.pad([p.B_Cu])),p.B_Cu)
 def test_multilayer_rejected(self):
  with self.assertRaises(ValueError):smd_copper_layer(self.pad([p.F_Cu,p.B_Cu]))
if __name__=='__main__':unittest.main()
