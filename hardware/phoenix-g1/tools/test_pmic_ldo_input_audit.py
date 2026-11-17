"""Negative topology tests; isolate pcbnew ownership/destruction per process."""
import subprocess,sys,unittest
from pathlib import Path
def run_case(name):
 import pcbnew as p
 from audit_pmic_ldo_inputs import audit_board,D
 b=p.LoadBoard(str(D/'pcb/ethernet-dvdd33-bypass.kicad_pcb'));held=[]
 if name in ['rxclkstrap','rxclkstrapground']:
  import json
  proof=json.loads((D/'pcb/ethernet-dvdd33-bypass.json').read_text());ids=set(proof['rxclk_route']['new_copper_uuids']);net='PHY_RXCLK' if name=='rxclkstrap' else 'GND'
  for t in list(b.GetTracks()):
   if t.m_Uuid.AsString() in ids and t.GetNetname()==net:b.Remove(t);held.append(t)
  assert held
  pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};b.BuildConnectivity()
  a=('R522','1') if name=='rxclkstrap' else ('R522','2');z=('R512','2') if name=='rxclkstrap' else ('U20','2')
  assert pads[z].m_Uuid.AsString() not in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads[a])}
  try:audit_board(b)
  except AssertionError as error:assert 'Required connection missing' in str(error),str(error)
  else:raise AssertionError('Broken RXCLK strap accepted')
  return
 if name=='resetpin':
  import json
  proof=json.loads((D/'pcb/ethernet-dvdd33-bypass.json').read_text());ids=set(proof['reset_route']['new_track_uuids'])
  for t in list(b.GetTracks()):
   if t.m_Uuid.AsString() in ids:b.Remove(t);held.append(t)
  assert len(held)==len(ids)
  pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};b.BuildConnectivity()
  assert pads['R515','2'].m_Uuid.AsString() not in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['U5','12'])}
  try:audit_board(b)
  except AssertionError as error:assert 'Required connection missing' in str(error),str(error)
  else:raise AssertionError('Missing PHY reset connection accepted')
  return
 if name=='inductor_back':
  f=next(f for f in b.GetFootprints() if f.GetReference()=='L501');f.Flip(f.GetPosition(),False)
  try:audit_board(b)
  except AssertionError as error:assert 'PHY inductor must remain on front' in str(error)
  else:raise AssertionError('Backside PHY inductor incorrectly accepted')
  return
 if name=='accepted':
  assert len(audit_board(b)['checks'])==195
  return
 if name in ['bypassdigital','bypassdigitalground','bypassanalog','bypassanalogground','iopower','avdd10','avdd10ground','iobypass','iobypassground','dvdd33','dvdd33ground']:
  stages={'avdd10':('ethernet-io-power-link', 'ethernet-avdd10-escape', '+1V0_PHY'),'avdd10ground':('ethernet-io-power-link', 'ethernet-avdd10-escape', 'GND'),'iobypass':('ethernet-avdd10-escape', 'ethernet-io-bypass-escape', '+3V3_PHY'),'iobypassground':('ethernet-avdd10-escape', 'ethernet-io-bypass-escape', 'GND'),'dvdd33':('ethernet-io-bypass-escape', 'ethernet-dvdd33-bypass', '+3V3_PHY'),'dvdd33ground':('ethernet-io-bypass-escape', 'ethernet-dvdd33-bypass', 'GND'),
   'bypassdigital':('ethernet-cap-grounds','ethernet-bypass-local','+1V0_PHY'),
   'bypassdigitalground':('ethernet-cap-grounds','ethernet-bypass-local','GND'),
   'bypassanalog':('ethernet-bypass-local','ethernet-avdd33-bypass','+3V3_PHY'),
   'bypassanalogground':('ethernet-bypass-local','ethernet-avdd33-bypass','GND'),
   'iopower':('ethernet-avdd33-bypass','ethernet-io-power-link','+3V3_PHY')}
  older,newer,net=stages[name]
  oldboard=p.LoadBoard(str(D/'pcb'/f'{older}.kicad_pcb'));newboard=p.LoadBoard(str(D/'pcb'/f'{newer}.kicad_pcb'))
  oldids={v.m_Uuid.AsString() for v in oldboard.GetTracks()}
  cutids={v.m_Uuid.AsString() for v in newboard.GetTracks() if v.m_Uuid.AsString() not in oldids and v.GetNetname()==net}
  if name in ['iopower','dvdd33ground']:
   ref,pin=('U5','28') if name=='iopower' else ('C519','2')
   pad=next(q for f in b.GetFootprints() if f.GetReference()==ref for q in f.Pads() if q.GetNumber()==pin)
   # Later routes can provide an alternate connection; isolate the pad locally.
   cutids={v.m_Uuid.AsString() for v in b.GetTracks() if v.GetNetname()==net and v.HitTest(pad.GetPosition(),p.FromMM(.6))}
  for v in list(b.GetTracks()):
   if v.m_Uuid.AsString() in cutids:b.Remove(v);held.append(v)
  assert held
  import json
  check=json.loads((D/'pcb'/f'{newer}.json').read_text())['checks'][1 if net=='GND' else 0]
  padmap={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
  a=padmap[tuple(check['from'].split('.'))];z=padmap[tuple(check['to'].split('.'))]
  b.BuildConnectivity()
  assert z.m_Uuid.AsString() not in {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(a)},'Fault injection did not disconnect the intended pair'
  try:audit_board(b)
  except AssertionError as error:assert 'Required connection missing' in str(error),str(error)
  else:raise AssertionError('Disconnected bypass incorrectly accepted')
  return
 if name in ['pullgrounds','buffercontrolgrounds','cspullup','reservoirpower','reservoirground','bleedpower','bleedground','blbase','blground','ethreset','ethresetground','ethstraps','ethcenter','ethcenterground','ethbias','xtalcapin','xtalcapout','xtalcapground','xtalground','xtalpin','xtalpout','ethcapgrounds']:
  older='display-buffer-feed' if name=='pullgrounds' else 'display-input-pulls'
  newer='display-input-pulls' if name=='pullgrounds' else 'display-input-returns'
  if name.startswith('reservoir'):older,newer='display-input-returns','display-reservoir'
  if name.startswith('bleed'):older,newer='display-reservoir','display-io-bleed'
  if name in ['blbase','blground','ethreset','ethresetground','ethstraps','ethcenter','ethcenterground','ethbias','xtalcapin','xtalcapout','xtalcapground','xtalground','xtalpin','xtalpout','ethcapgrounds']:older,newer='display-io-bleed','display-backlight-control'
  if name in ['ethreset','ethresetground']:older,newer='display-backlight-control','ethernet-reset-passives'
  if name=='ethstraps':older,newer='ethernet-reset-passives','ethernet-strap-grounds'
  if name in ['ethcenter','ethcenterground','ethbias','xtalcapin','xtalcapout','xtalcapground','xtalground','xtalpin','xtalpout','ethcapgrounds']:older,newer='ethernet-strap-grounds','ethernet-center-tap'
  if name=='ethbias':older,newer='ethernet-center-tap','ethernet-bias-grounds'
  if name in ['xtalcapin','xtalcapout','xtalcapground']:older,newer='ethernet-bias-grounds','ethernet-clock-placement'
  if name=='xtalground':older,newer='ethernet-clock-placement','ethernet-clock-grounds'
  if name in ['xtalpin','xtalpout','ethcapgrounds']:older,newer='ethernet-clock-grounds','ethernet-clock-pins'
  if name=='ethcapgrounds':older,newer='ethernet-clock-pins','ethernet-cap-grounds'
  base=p.LoadBoard(str(D/'pcb'/f'{older}.kicad_pcb'));stage=p.LoadBoard(str(D/'pcb'/f'{newer}.kicad_pcb'))
  ids={t.m_Uuid.AsString() for t in base.GetTracks()}
  cut_ids={t.m_Uuid.AsString() for t in stage.GetTracks() if t.m_Uuid.AsString() not in ids and t.GetNetname()==('+3V3_IO' if name in ['cspullup','bleedpower'] else 'PHY_XIN' if name in ['xtalcapin','xtalpin'] else 'PHY_XOUT' if name in ['xtalcapout','xtalpout'] else 'PHY_RESET_N' if name=='ethreset' else 'ETH_CENTER_TAP' if name=='ethcenter' else 'LCD_BL_BASE' if name=='blbase' else '+3V0_LCD' if name=='reservoirpower' else 'GND')}
 for t in list(b.GetTracks()):
  if name in ['mosi','sclk','dc','reset','cs','pullgrounds','buffercontrolgrounds','cspullup','reservoirpower','reservoirground','bleedpower','bleedground','blbase','blground','ethreset','ethresetground','ethstraps','ethcenter','ethcenterground','ethbias','xtalcapin','xtalcapout','xtalcapground','xtalground','xtalpin','xtalpout','ethcapgrounds']:
   nets={'mosi':'LCD_MOSI','sclk':'LCD_SCLK','dc':'LCD_DC','reset':'LCD_RESET_N','cs':'LCD_CS_N'}
   cut=t.GetNetname()==nets[name] if name in nets else t.m_Uuid.AsString() in cut_ids
   if name=='xtalcapout':
    cap=next(q for f in b.GetFootprints() if f.GetReference()=='C521' for q in f.Pads() if q.GetNumber()=='1')
    cut=t.GetNetname()=='PHY_XOUT' and t.HitTest(cap.GetPosition(),p.FromMM(.5))
   if cut:b.Remove(t);held.append(t)
   continue
  if name in ['vcc9via','tp4via','sourcefeed','r410input','vdcpassives','cpufeed','tp3','displayfeed','displayenable','bufferbypass','bufferground','bufferfeed']:
   cut=False
   if name=='displayenable':
    cut=isinstance(t,p.PCB_VIA) and t.GetNetname()=='+3V3_IO' and t.GetPosition()==p.VECTOR2I(p.FromMM(28.3),p.FromMM(30.25))
   elif name in ['bufferbypass','bufferground']:
    xy=(22.07,22.13) if name=='bufferbypass' else (21.1,21.52)
    cut=not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu and t.GetStart()==p.VECTOR2I(*(p.FromMM(v) for v in xy))
   elif name=='bufferfeed':
    cut=not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.In2_Cu and t.GetNetname()=='+3V0_LCD'
   elif name=='displayfeed':
    cut=not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu and t.GetNetname()=='+5V_MAIN' and t.GetStart()==p.VECTOR2I(p.FromMM(30.2),p.FromMM(22))
   elif name=='tp3':
    cut=isinstance(t,p.PCB_VIA) and t.GetNetname()=='+5V_MAIN' and t.GetPosition()==p.VECTOR2I(p.FromMM(45.6),p.FromMM(32.5))
   elif name=='cpufeed':
    cut=isinstance(t,p.PCB_VIA) and t.GetNetname()=='+5V_MAIN' and t.GetPosition()==p.VECTOR2I(p.FromMM(64.5),p.FromMM(20.5))
   elif name in ['vcc9via','tp4via']:
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
 def test_rxclk_strap_interruption(self):self.check('rxclkstrap')
 def test_rxclk_strap_ground_interruption(self):self.check('rxclkstrapground')
 def test_phy_reset_pin_interruption(self):self.check('resetpin')
 def check(self,name):
  r=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--case',name],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_avdd10_interruption(self):self.check('avdd10')
 def test_avdd10ground_interruption(self):self.check('avdd10ground')
 def test_iobypass_interruption(self):self.check('iobypass')
 def test_iobypassground_interruption(self):self.check('iobypassground')
 def test_dvdd33_interruption(self):self.check('dvdd33')
 def test_dvdd33ground_interruption(self):self.check('dvdd33ground')
 def test_digital_bypass_interruption(self):self.check('bypassdigital')
 def test_digital_bypass_ground_interruption(self):self.check('bypassdigitalground')
 def test_analog_bypass_interruption(self):self.check('bypassanalog')
 def test_analog_bypass_ground_interruption(self):self.check('bypassanalogground')
 def test_phy_io_power_interruption(self):self.check('iopower')
 def test_ethernet_cap_ground_interruption(self):self.check('ethcapgrounds')
 def test_crystal_cap_input_interruption(self):self.check('xtalcapin')
 def test_crystal_cap_output_interruption(self):self.check('xtalcapout')
 def test_crystal_cap_ground_interruption(self):self.check('xtalcapground')
 def test_crystal_ground_interruption(self):self.check('xtalground')
 def test_crystal_phy_input_interruption(self):self.check('xtalpin')
 def test_crystal_phy_output_interruption(self):self.check('xtalpout')
 def test_ethernet_bias_ground_interruption(self):self.check('ethbias')
 def test_ethernet_reset_interruption(self):self.check('ethreset')
 def test_ethernet_reset_ground_interruption(self):self.check('ethresetground')
 def test_ethernet_strap_ground_interruption(self):self.check('ethstraps')
 def test_ethernet_center_tap_interruption(self):self.check('ethcenter')
 def test_ethernet_center_tap_ground_interruption(self):self.check('ethcenterground')
 def test_backlight_base_interruption(self):self.check('blbase')
 def test_backlight_ground_interruption(self):self.check('blground')
 def test_bleed_power_interruption(self):self.check('bleedpower')
 def test_bleed_ground_interruption(self):self.check('bleedground')
 def test_reservoir_power_interruption(self):self.check('reservoirpower')
 def test_reservoir_ground_interruption(self):self.check('reservoirground')
 def test_mosi_pull_interruption(self):self.check('mosi')
 def test_clock_pull_interruption(self):self.check('sclk')
 def test_dc_pull_interruption(self):self.check('dc')
 def test_reset_pull_interruption(self):self.check('reset')
 def test_cs_pull_interruption(self):self.check('cs')
 def test_pull_ground_interruption(self):self.check('pullgrounds')
 def test_buffer_control_ground_interruption(self):self.check('buffercontrolgrounds')
 def test_cs_pullup_feed_interruption(self):self.check('cspullup')
 def test_display_enable_interruption(self):self.check('displayenable')
 def test_buffer_bypass_interruption(self):self.check('bufferbypass')
 def test_buffer_ground_interruption(self):self.check('bufferground')
 def test_buffer_feed_interruption(self):self.check('bufferfeed')
 def test_display_feed_interruption(self):self.check('displayfeed')
 def test_cpu_input_feed_interruption(self):self.check('cpufeed')
 def test_tp3_interruption(self):self.check('tp3')
 def test_backside_inductor_rejected(self):self.check('inductor_back')
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
