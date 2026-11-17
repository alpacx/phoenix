#!/usr/bin/env python3
import unittest
import pcbnew as p
from pcb_route_guards import require_constant_width_branch

class BranchGuards(unittest.TestCase):
    def setUp(self):
        self.board=p.BOARD()
        for name in ['GND','VDD']:self.board.Add(p.NETINFO_ITEM(self.board,name))
        self.tracks=[]
        for a,b in [((1,1),(2,1)),((2,1),(2,2))]:
            t=p.PCB_TRACK(self.board);t.SetStart(p.VECTOR2I(*(p.FromMM(v) for v in a)));t.SetEnd(p.VECTOR2I(*(p.FromMM(v) for v in b)))
            t.SetLayer(p.F_Cu);t.SetWidth(p.FromMM(.8));t.SetNetCode(self.board.GetNetcodeFromNetname('GND'));self.board.Add(t);self.tracks.append(t)
    def check(self):
        return require_constant_width_branch(self.tracks,net='GND',layer=p.F_Cu,width_mm=.8,start_mm=(1,1),end_mm=(2,2))
    def test_preserved(self):self.assertTrue(self.check()['width_preserved'])
    def test_narrowed_segment(self):
        self.tracks[1].SetWidth(p.FromMM(.2))
        with self.assertRaisesRegex(AssertionError,'width'):self.check()
    def test_gap(self):
        self.tracks[1].SetStart(p.VECTOR2I(p.FromMM(2.1),p.FromMM(1)))
        with self.assertRaisesRegex(AssertionError,'discontinuous'):self.check()
    def test_wrong_net(self):
        self.tracks[1].SetNetCode(self.board.GetNetcodeFromNetname('VDD'))
        with self.assertRaisesRegex(AssertionError,'net'):self.check()
    def test_wrong_layer(self):
        self.tracks[1].SetLayer(p.B_Cu)
        with self.assertRaisesRegex(AssertionError,'layer'):self.check()
    def test_wrong_endpoint(self):
        self.tracks[1].SetEnd(p.VECTOR2I(p.FromMM(2),p.FromMM(3)))
        with self.assertRaisesRegex(AssertionError,'endpoint'):self.check()

if __name__=='__main__':unittest.main()
