#!/usr/bin/env python3
"""Fault injection for persisted PHY corridor copper, isolated per KiCad process."""
import hashlib,json,unittest,subprocess,sys,os
from pathlib import Path
import pcbnew as p
from pcb_route_guards import require_constant_width_branch
S=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-compact-inductor/corridor'
r=json.loads((S/'checkpoint.json').read_text());source=S/r['board']
class Corridor(unittest.TestCase):
 def setUp(self):
  self.b=p.LoadBoard(str(source));self.b.BuildConnectivity();self.pads={(f.GetReference(),q.GetNumber()):q for f in self.b.GetFootprints() for q in f.Pads()}
 def tearDown(self):self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),r['sha256'])
 def branch(self,path,net):
  tracks=[]
  for a,z in zip(path,path[1:]):
   if tuple(p.FromMM(v) for v in a)==tuple(p.FromMM(v) for v in z):continue
   found=[t for t in self.b.GetTracks() if not isinstance(t,p.PCB_VIA) and t.GetNetname()==net and tuple(t.GetStart())==tuple(p.FromMM(v) for v in a) and tuple(t.GetEnd())==tuple(p.FromMM(v) for v in z)]
   self.assertEqual(len(found),1);tracks.extend(found)
  return tracks
 def guard(self,path,net,width):return require_constant_width_branch(self.branch(path,net),net=net,layer=p.F_Cu,width_mm=width,start_mm=path[0],end_mm=path[-1])
 def connected(self,a,z):
  self.b.BuildConnectivity();return self.pads[z].m_Uuid.AsString() in {q.m_Uuid.AsString() for q in self.b.GetConnectivity().GetConnectedItems(self.pads[a])}
 def test_input_and_returns_connected(self):
  self.guard(r['input_path_mm'],'+3V3_PHY',1.05)
  for a,z in [(('C515','1'),('C517','1')),(('C515','1'),('U5','28')),(('C515','1'),('U5','29')),(('C515','2'),('C1001','2')),(('C511','2'),('C515','2'))]:self.assertTrue(self.connected(a,z),(a,z))
 def test_cut_input_detected(self):
  removed=self.branch(r['input_path_mm'],'+3V3_PHY')
  for t in removed:self.b.Remove(t)
  self.assertFalse(self.connected(('C515','1'),('C517','1')))
 def test_input_narrowing_rejected(self):
  self.branch(r['input_path_mm'],'+3V3_PHY')[0].SetWidth(p.FromMM(.2))
  with self.assertRaisesRegex(AssertionError,'width'):self.guard(r['input_path_mm'],'+3V3_PHY',1.05)
 def test_bulk_return_width(self):
  path=r['source_reports']['bulk-return-probe']['new_ground_path_mm'];self.guard(path,'GND',.5)
  ids=set(r['source_reports']['output-return-probe']['changed']);tracks=[t for t in self.b.GetTracks() if t.m_Uuid.AsString() in ids];self.assertEqual(len(tracks),3)
  for t in tracks:self.assertEqual(t.GetWidth(),p.FromMM(.5))
 def test_return_narrowing_rejected(self):
  path=r['source_reports']['bulk-return-probe']['new_ground_path_mm'];self.branch(path,'GND')[0].SetWidth(p.FromMM(.2))
  with self.assertRaisesRegex(AssertionError,'width'):self.guard(path,'GND',.5)
 def test_rxclk_strap_connected(self):
  self.assertIn('rxclk-strap',r['source_reports'])
  self.assertTrue(self.connected(('R522','1'),('R512','2')));self.assertTrue(self.connected(('R522','2'),('C515','2')))
  self.assertLessEqual(r['source_reports']['rxclk-strap']['strap_length_mm'],2.5)
 def test_cut_rxclk_strap_detected(self):
  proof=r['source_reports']['rxclk-strap'];removed=self.branch(proof['strap_path_mm'],'PHY_RXCLK')
  for t in removed:self.b.Remove(t)
  self.assertFalse(self.connected(('R522','1'),('R512','2')))
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='--case':
  name=sys.argv[2];sys.argv=[sys.argv[0],'Corridor.'+name];result=unittest.main(exit=False).result;sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
 else:
  names=unittest.defaultTestLoader.getTestCaseNames(Corridor)
  for name in names:
   result=subprocess.run([sys.executable,__file__,'--case',name],capture_output=True,text=True)
   if result.returncode:print(result.stdout+result.stderr);raise SystemExit(result.returncode)
   print(name+': PASS',flush=True)
  print(str(len(names))+' isolated CAD tests passed.')
