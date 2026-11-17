#!/usr/bin/env python3
"""Dimensional and fault-injection tests for the experimental compact PHY PCB."""
import hashlib,json,unittest,subprocess,sys,os
from pathlib import Path
import pcbnew as p
from pcb_route_guards import require_constant_width_branch
H=Path(__file__).resolve().parents[1]
S=H/'migration-rk3562/experiments/phy-compact-inductor'
record=json.loads((S/'study-checkpoint.json').read_text());source=S/record['board']

class CompactStudy(unittest.TestCase):
 def setUp(self):
  self.board=p.LoadBoard(str(source));self.board.BuildConnectivity()
  self.pads={(f.GetReference(),q.GetNumber()):q for f in self.board.GetFootprints() for q in f.Pads()}
 def tearDown(self):self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),record['candidate_sha256'])
 def branch(self):
  result=[]
  for a,z in zip(record['path_mm'],record['path_mm'][1:]):
   matches=[t for t in self.board.GetTracks() if not isinstance(t,p.PCB_VIA) and tuple(t.GetStart())==tuple(p.FromMM(v) for v in a) and tuple(t.GetEnd())==tuple(p.FromMM(v) for v in z) and t.GetNetname()=='+1V0_PHY']
   self.assertEqual(len(matches),1);result.extend(matches)
  return result
 def guard(self):
  return require_constant_width_branch(self.branch(),net='+1V0_PHY',layer=p.F_Cu,width_mm=1.55,start_mm=record['path_mm'][0],end_mm=record['path_mm'][-1])
 def connected(self):
  self.board.BuildConnectivity()
  return self.pads['C511','1'].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in self.board.GetConnectivity().GetConnectedItems(self.pads['L501','2'])}
 def test_manufacturer_land_pattern(self):
  a,z=self.pads['L501','1'],self.pads['L501','2']
  for q in [a,z]:self.assertEqual(tuple(q.GetSize()),(p.FromMM(.95),p.FromMM(2.1)))
  self.assertAlmostEqual(abs(p.ToMM(a.GetPosition().x-z.GetPosition().x)),1.65)
  self.assertAlmostEqual(1.65-.95,.7)
  self.assertAlmostEqual(1.65+.95,2.6)
 def test_output_connected_full_width(self):
  self.assertTrue(self.connected());self.assertTrue(self.guard()['width_preserved'])
 def test_narrowing_rejected(self):
  self.branch()[0].SetWidth(p.FromMM(.2))
  with self.assertRaisesRegex(AssertionError,'width'):self.guard()
 def test_cut_output_detected(self):
  removed=self.branch()
  for t in removed:self.board.Remove(t)
  self.assertFalse(self.connected())
 def test_pad_identities_preserved(self):
  baseline=S/'baseline/source.kicad_pcb'
  self.assertEqual(hashlib.sha256(baseline.read_bytes()).hexdigest(),record['source_sha256'])
  b=p.LoadBoard(str(baseline));old={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
  for ref in ['L501','C511','C515','R516']:
   for num in ['1','2']:
    self.assertEqual(old[ref,num].m_Uuid.AsString(),self.pads[ref,num].m_Uuid.AsString());self.assertEqual(old[ref,num].GetNetname(),self.pads[ref,num].GetNetname())

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='--case':
  name=sys.argv[2];sys.argv=[sys.argv[0],'CompactStudy.'+name]
  result=unittest.main(exit=False).result
  sys.stdout.flush();sys.stderr.flush()
  os._exit(0 if result.wasSuccessful() else 1)  # Avoid KiCad SWIG shutdown crash after fault injection.
 else:
  names=unittest.defaultTestLoader.getTestCaseNames(CompactStudy)
  for name in names:
   result=subprocess.run([sys.executable,__file__,'--case',name],capture_output=True,text=True)
   if result.returncode:print(result.stdout+result.stderr);raise SystemExit(result.returncode)
   print(name+': PASS')
  print(str(len(names))+' isolated CAD tests passed.')
