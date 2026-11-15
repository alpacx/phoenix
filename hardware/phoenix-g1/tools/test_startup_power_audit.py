"""Negative topology tests; isolate pcbnew ownership/destruction per process."""
import subprocess,sys,unittest
from pathlib import Path
def run_case(name):
 import pcbnew as p
 from audit_startup_power import audit_board,D
 b=p.LoadBoard(str(D/'pcb/cpu-enable.kicad_pcb'));held=[]
 if name=='accepted':
  assert len(audit_board(b)['checks'])==64
  return
 for t in list(b.GetTracks()):
  if t.GetNetname()==name:b.Remove(t);held.append(t)
 assert held
 try:audit_board(b)
 except AssertionError as error:
  assert 'Required connection missing' in str(error),str(error)
 else:raise AssertionError('Disconnected circuit incorrectly accepted')
class StartupAuditTests(unittest.TestCase):
 def check(self,name):
  r=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--case',name],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_accepted_board(self):self.check('accepted')
 def test_switch_interruption_detected(self):self.check('CPU_SW')
 def test_feedback_interruption_detected(self):self.check('CPU_FB_SENSE')
if __name__=='__main__':
 if len(sys.argv)==3 and sys.argv[1]=='--case':run_case(sys.argv[2])
 else:unittest.main()
