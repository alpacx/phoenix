#!/usr/bin/env python3
"""Geometry regressions for bounded multi-target escape search; run with KiCad Python."""
import math,unittest
import pcbnew as p
from local_pcb_router import LocalRouter
class ReachabilityTest(unittest.TestCase):
 def setUp(self):self.board=p.BOARD();self.router=LocalRouter(self.board,(0,0,4,4),grid=1)
 def test_barrier_and_single_opening(self):
  blocked={(2,y) for y in range(5)}
  self.assertIsNone(self.router.path_from_tree(self.router.paths_from(blocked,(0,2),10),(4,2)))
  blocked.remove((2,2));tree=self.router.paths_from(blocked,(0,2),5);path=self.router.path_from_tree(tree,(4,2))
  self.assertEqual(path,[(0,2),(4,2)])
  self.assertAlmostEqual(tree['distances'][4,2],4)
 def test_corner_cannot_be_cut(self):
  tree=self.router.paths_from({(1,0),(0,1)},(0,0),10)
  self.assertEqual(set(tree['distances']),{(0,0)})
 def test_distance_budget_and_invalid_start(self):
  tree=self.router.paths_from(set(),(0,0),4)
  self.assertIsNone(self.router.path_from_tree(tree,(3,3)))
  self.assertIsNotNone(self.router.path_from_tree(tree,(2,2)))
  self.assertFalse(self.router.paths_from({(0,0)},(0,0),4)['distances'])
  self.assertFalse(self.router.paths_from(set(),(-1,0),4)['distances'])
if __name__=='__main__':unittest.main()
