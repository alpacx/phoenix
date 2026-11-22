"""Reversed-face and rotation checks for the asymmetric antenna edge reservation."""
import unittest
import math
from w3006_layout1_geometry import xy_nm,GROUND,LAND_CENTERS,HIGH,LOW
class W3006MaskTest(unittest.TestCase):
 def test_length_handedness_and_board_edge(self):
  for side in ('top','bottom','left','right'):
   for mirrored in (False,True):
    xf=lambda u,v:xy_nm(side,3,mirrored,u,v,(0,0,90,40))
    origin=xf(0,0);a=xf(*LAND_CENTERS['1']);z=xf(*LAND_CENTERS['2']);dx=tuple(t-o for t,o in zip(xf(1,0),origin));dy=tuple(t-o for t,o in zip(xf(0,1),origin))
    self.assertEqual(math.dist(a,z),9100000)
    self.assertEqual(dx[0]*dy[1]-dx[1]*dy[0],(1 if mirrored else -1)*10**12)
    self.assertEqual(math.dist(xf(LOW,0),xf(HIGH,0)),18290000)
    near_edge=lambda pt: {'top':pt[1],'bottom':40000000-pt[1],'left':pt[0],'right':90000000-pt[0]}[side]
    self.assertEqual(near_edge(origin),0)
    self.assertEqual(near_edge(a),2000000)
    self.assertEqual(near_edge(z),2000000)
    self.assertEqual(max(near_edge(xf(*q)) for q in GROUND),6250000)
if __name__=='__main__':unittest.main()
