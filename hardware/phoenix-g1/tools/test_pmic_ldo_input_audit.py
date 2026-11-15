"""Negative topology tests; isolate pcbnew ownership/destruction per process."""
import subprocess,sys,unittest
from pathlib import Path
def run_case(name):
 import pcbnew as p
 from audit_pmic_ldo_inputs import audit_board,D
 b=p.LoadBoard(str(D/'pcb/vdc-passives.kicad_pcb'));held=[]
 if name=='accepted':
  assert len(audit_board(b)['checks'])==117
  return
 for t in list(b.GetTracks()):
  if name in ['vcc9via','tp4via','sourcefeed','r410input','vdcpassives']:
   cut=False
   if name in ['vcc9via','tp4via']:
    q=(60.4,3.7) if name=='vcc9via' else (55.5,38.5)
    cut=isinstance(t,p.PCB_VIA) and t.GetNetname()=='+3V3_SYS' and (t.GetPosition()-p.VECTOR2I(*(p.FromMM(v) for v in q))).EuclideanNorm()<=10
   elif name=='vdcpassives':cut=t.GetNetname()=='PMIC_VDC'
   else:
    q=(18.55,37.3) if name=='sourcefeed' else (59.1,5.4)
    layer=p.In4_Cu if name=='sourcefeed' else p.B_Cu
    cut=not isinstance(t,p.PCB_VIA) and t.GetLayer()==layer and t.GetNetname()=='+3V3_SYS' and (t.GetStart()-p.VECTOR2I(*(p.FromMM(v) for v in q))).EuclideanNorm()<=10
   if cut:b.Remove(t);held.append(t)
   continue
  if name in ['ground481','ground484','upperpower']:
   layer=p.In4_Cu if name=='upperpower' else p.B_Cu
   start={'ground481':(59.52,4),'ground484':(57.02,4),'upperpower':(55.65,6.6)}[name]
   end=(55.65,5.2) if name=='upperpower' else None
   if not isinstance(t,p.PCB_VIA) and t.GetLayer()==layer and t.GetStart()==p.VECTOR2I(*(p.FromMM(v) for v in start)) and (end is None or t.GetEnd()==p.VECTOR2I(*(p.FromMM(v) for v in end))):b.Remove(t);held.append(t)
   continue
  if name=='rtc':
   if t.GetNetname()=='+3V3_SYS' and not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.In4_Cu and (t.GetStart()-p.VECTOR2I(p.FromMM(66.1),p.FromMM(8.1))).EuclideanNorm()<=10:b.Remove(t);held.append(t)
   continue
  if name=='buck':
   if t.GetNetname()=='+3V3_SYS' and not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu and t.GetStart()==p.VECTOR2I(p.FromMM(54.95),p.FromMM(9)) and t.GetEnd()==p.VECTOR2I(p.FromMM(54),p.FromMM(9.4)):b.Remove(t);held.append(t)
   continue
  if name=='rail':
   if t.GetNetname()=='+3V3_SYS' and not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.In4_Cu and t.GetStart()==p.VECTOR2I(p.FromMM(54),p.FromMM(9.4)):b.Remove(t);held.append(t)
   continue
  if t.GetNetname()=='+3V3_SYS' and not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu and t.GetStart()==p.VECTOR2I(p.FromMM({'vcc7':56.59,'vcc8':61.05,'vcc6':61.4,'vcc5':58.6,'audio':62.45,'vcc4':57.9,'rtc':64.55}[name]),p.FromMM({'vcc7':7.25,'vcc8':5.59,'vcc6':12.41,'vcc5':12.41,'audio':12.41,'vcc4':5.59,'rtc':6.5}[name])):b.Remove(t);held.append(t)
 assert held
 try:audit_board(b)
 except AssertionError as error:
  assert 'Required connection missing' in str(error),str(error)
 else:raise AssertionError('Disconnected circuit incorrectly accepted')
class PmicInputAuditTests(unittest.TestCase):
 def check(self,name):
  r=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--case',name],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_accepted_board(self):self.check('accepted')
 def test_vcc7_interruption_detected(self):self.check('vcc7')
 def test_vcc8_interruption_detected(self):self.check('vcc8')
 def test_vcc6_interruption_detected(self):self.check('vcc6')
 def test_vcc5_interruption_detected(self):self.check('vcc5')
 def test_audio_interruption_detected(self):self.check('audio')
 def test_rail_interruption_detected(self):self.check('rail')
 def test_buck_link_interruption_detected(self):self.check('buck')
 def test_c481_ground_interruption(self):self.check('ground481')
 def test_c484_ground_interruption(self):self.check('ground484')
 def test_upper_power_interruption(self):self.check('upperpower')
 def test_vcc4_interruption(self):self.check('vcc4')
 def test_rtc_link_interruption(self):self.check('rtc')
 def test_vcc9_via_interruption(self):self.check('vcc9via')
 def test_tp4_via_interruption(self):self.check('tp4via')
 def test_source_feed_interruption(self):self.check('sourcefeed')
 def test_r410_input_interruption(self):self.check('r410input')
 def test_vdc_passives_interruption(self):self.check('vdcpassives')
if __name__=='__main__':
 if len(sys.argv)==3 and sys.argv[1]=='--case':run_case(sys.argv[2])
 else:unittest.main()
