"""Regression: returning Y501 to its old position must expose H8105 conflict."""
import json,unittest
import pcbnew as p
from audit_mount_component_reservations import D,screen
class MountScreenTests(unittest.TestCase):
 def test_crystal_return_to_reserved_mount_detected(self):
  cp=json.loads((D/'working-candidate.json').read_text());b=p.LoadBoard(str(D/cp['board']))
  key=lambda row:(row['reservation'],row['ref'])
  conflict=('H8105 mechanical reservation','Y501')
  self.assertNotIn(conflict,{key(row) for row in screen(b)})
  f=next(f for f in b.GetFootprints() if f.GetReference()=='Y501');f.SetPosition(p.VECTOR2I(p.FromMM(68.5),p.FromMM(33)));f.SetOrientationDegrees(0)
  self.assertIn(conflict,{key(row) for row in screen(b)})
if __name__=='__main__':unittest.main()
