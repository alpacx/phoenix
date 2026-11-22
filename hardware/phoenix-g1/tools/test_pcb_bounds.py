import unittest
import pcbnew as p
from pcb_bounds import inflated_box, point_distance_squared

class BoundsLifetimeTest(unittest.TestCase):
    def test_bounds_are_owned_after_expansion(self):
        board=p.BOARD()
        line=p.PCB_TRACK(board)
        line.SetWidth(200000)
        line.SetStart(p.VECTOR2I(1000000,2000000))
        line.SetEnd(p.VECTOR2I(3000000,2000000))
        original=line.GetBoundingBox()
        enlarged=inflated_box(line,250000)
        # Native allocations after the helper must not alter the returned box.
        unrelated=[p.BOX2I(p.VECTOR2I(i,i),p.VECTOR2I(40,80)) for i in range(100)]
        self.assertTrue(enlarged.thisown)
        self.assertEqual(enlarged.GetLeft(),original.GetLeft()-250000)
        self.assertEqual(enlarged.GetWidth(),original.GetWidth()+500000)
        self.assertNotEqual(enlarged.GetLeft(),unrelated[-1].GetLeft())

    def test_rectangle_distance_in_all_quadrants(self):
        box=p.BOX2I(p.VECTOR2I(10,20),p.VECTOR2I(1,2))
        for x,dx in ((8,2),(10,0),(15,4)):
            for y,dy in ((13,7),(21,0),(25,3)):
                self.assertEqual(point_distance_squared(box,p.VECTOR2I(x,y)),dx*dx+dy*dy)

if __name__=='__main__':
    unittest.main()
