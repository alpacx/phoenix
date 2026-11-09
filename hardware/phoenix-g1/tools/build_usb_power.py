#!/usr/bin/env python3
"""Type-C current-qualified USB sink power draft, based on TI datasheets."""
from schematic_builder import *
import sexpdata as sx

def main():
 syms=load_symbols([],['R','C','L'])
 for code in ['C2155674','C404027','C43698','C81563','C113520','C7827','C7666']:
  lib=sx.loads((ROOT/f'kicad/Import_{code}.kicad_sym').read_text())
  for s in fields(lib,'symbol'):
   for prop in fields(s,'property'):prop[:]=[v for v in prop if not(isinstance(v,list) and v and str(v[0])=='id')]
   syms[s[1]]=s
  fp=ROOT/'kicad/fp-lib-table';text=fp.read_text()
  if f'(name "Import_{code}")' not in text:fp.write_text(text.rstrip()[:-1]+f' (lib (name "Import_{code}")(type "KiCad")(uri "${{KIPRJMOD}}/Import_{code}.pretty")(options "")(descr "Imported; geometry pending audit"))\n)\n')
 expected={
 'SN74LVC1G08DBVR':{'1':'A','2':'B','3':'GND','4':'Y','5':'VCC'},
 'TLV75533PDBVR':{'1':'IN','2':'GND','3':'EN','4':'NC','5':'OUT'},
 'TPS3808G33DBVR':{'1':'~{RESET}','2':'GND','3':'~{MR}','4':'CT','5':'SENSE','6':'VDD'},
 'TPS259531DSGR':{'1':'dVdt','2':'EN/UVLO','3':'IN','4':'IN','5':'OUT','6':'~{FLT}','7':'ILM','8':'GND','9':'GND'},
 'SN74LVC1G02DCKR':{'1':'B','2':'A','3':'GND','4':'Y','5':'VCC'},
 'SN74LVC1G04DBVR':{'1':'N.C','2':'A','3':'GND','4':'Y','5':'VCC'},
 'TPS62132RGTR':{str(i+1):n for i,n in enumerate('SW SW SW PG FB AGND FSW DEF SS/TR AVIN PVIN PVIN EN VOS PGND PGND EP'.split())}}
 for name,mapping in expected.items():
  assert mapping=={str(fields(p,'number')[0][1]):fields(p,'name')[0][1] for p in walk(syms[name],'pin')},name
  for p in walk(syms[name],'pin'):
   n=fields(p,'name')[0][1];num=str(fields(p,'number')[0][1]);kind='input'
   if n in ['IN','GND','VCC','VDD','AGND','PGND','EP','AVIN','PVIN']:kind='power_in'
   elif n in ['OUT','SW']:kind='power_out'
   elif n in ['~{RESET}','~{FLT}','PG']:kind='open_collector'
   elif n=='Y':kind='output'
   elif n in ['NC','N.C']:kind='no_connect'
   elif n in ['dVdt','ILM','CT','SS/TR']:kind='passive'
   if name=='TPS62132RGTR' and n=='SW' and num!='1':kind='passive'
   p[1]=sx.Symbol(kind)
 save_library('Phoenix_InputPower',syms)
 def r(sh,ref,x,y,a,b,val):sh.place('R',ref,x,y,{'1':a,'2':b},val,'Phoenix_Passives:R_0603_1608Metric' if ref=='R1201' else 'Phoenix_Passives:R_0402_1005Metric')
 def c(sh,ref,x,y,a,val,large=False):sh.place('C',ref,x,y,{'1':a,'2':'GND'},val,'Phoenix_Passives:C_0805_2012Metric' if large else 'Phoenix_Passives:C_0402_1005Metric')
 sh=Sheet('usb-power-control','Phoenix G1 - Type-C current admission and startup','Phoenix_InputPower',syms)
 sh.place('TLV75533PDBVR','U11',60.96,45.72,{'1':'VBUS_PROTECTED','2':'GND','3':'VBUS_PROTECTED','4':None,'5':'+3V3_AON'},mpn='TLV75533PDBVR')
 sh.place('TPS3808G33DBVR','U12',172.72,45.72,{'1':'AON_READY','2':'GND','3':'+3V3_AON','4':None,'5':'+3V3_AON','6':'+3V3_AON'},mpn='TPS3808G33DBVR')
 sh.place('SN74LVC1G04DBVR','U13',304.8,45.72,{'1':None,'2':'AON_READY','3':'GND','4':'USB_CC_ENABLE_N','5':'+3V3_AON'},mpn='SN74LVC1G04DBVR')
 sh.place('SN74LVC1G02DCKR','U14',91.44,142.24,{'1':'CC_OUT1_N','2':'CC_OUT2_N','3':'GND','4':'USB_CURRENT_OK','5':'+3V3_AON'},mpn='SN74LVC1G02DCKR')
 sh.place('SN74LVC1G08DBVR','U19',223.52,142.24,{'1':'USB_CURRENT_OK','2':'AON_READY','3':'GND','4':'USB_MAIN_ENABLE','5':'+3V3_AON'},mpn='SN74LVC1G08DBVR')
 sh.place('SN74LVC1G04DBVR','U16',304.8,142.24,{'1':None,'2':'RESET_N','3':'GND','4':'USB_MUX_ENABLE_N','5':'+3V3_AON'},mpn='SN74LVC1G04DBVR')
 for ref,x,y,a,b,val in [('R1101',228.6,45.72,'+3V3_AON','AON_READY','100k'),('R1102',172.72,142.24,'USB_MAIN_ENABLE','GND','47k'),('R1103',365.76,142.24,'RESET_N','GND','100k')]:r(sh,ref,x,y,a,b,val)
 for i,(x,a,val) in enumerate([(30.48,'VBUS_PROTECTED','1u / 10V'),(91.44,'+3V3_AON','2.2u / 10V'),(152.4,'+3V3_AON','100n'),(213.36,'+3V3_AON','100n'),(274.32,'+3V3_AON','100n'),(335.28,'+3V3_AON','100n')]):c(sh,f'C{1101+i}',x,208.28,a,val)
 for i,t in enumerate(['U12 open CT gives 20ms typical delay after 3.3V AON is valid; qualify minimum delay against HD3SS3220.', 'NOR truth table admits main power only when OUT1=0 AND OUT2=0: Type-C 3A advertisement.', 'Default-current and 1.5A sources leave main rails off. This design does not negotiate USB PD.', 'SS mux remains disabled until PMIC releases RESET_N after system rails sequence.', 'No host-power backfeed path intended. Validate attach/detach, brownout, CC-state changes and USB suspend.', 'Input +3V3_AON current and total connector-side capacitance require USB compliance verification.']):sh.note(t,20,245+i*6)
 c(sh,'C1107',365.76,208.28,'+3V3_AON','100n')
 sh.note('U19 AND gates the current advertisement with AON supervisor readiness; validate ramp behavior.',20,281)
 sh.save()
 fuse=Sheet('usb-input-protection','Phoenix G1 - USB input eFuse','Phoenix_InputPower',syms)
 fuse.place('TPS259531DSGR','U15',101.6,66.04,{'1':'USB_DVDT','2':'USB_MAIN_ENABLE','3':'VBUS_PROTECTED','4':'VBUS_PROTECTED','5':'+5V_MAIN','6':'USB_POWER_FAULT_N','7':'USB_ILIM','8':'GND','9':'GND'},mpn='TPS259531DSGR')
 r(fuse,'R1201',213.36,66.04,'USB_ILIM','GND','806R 1%')
 r(fuse,'R1202',304.8,66.04,'USB_POWER_FAULT_N','+3V3_AON','100k')
 c(fuse,'C1201',40.64,142.24,'VBUS_PROTECTED','1u / 10V')
 c(fuse,'C1202',132.08,142.24,'USB_DVDT','22n / 10V')
 c(fuse,'C1203',223.52,142.24,'+5V_MAIN','1u / 10V')
 for i,t in enumerate(['TPS259531: active-high enable, auto-retry, 5.7V typical overvoltage clamp; not an accurate 5V regulator.', 'RILM=806R targets 2000/R +0.04 = 2.521A typical. Validate guaranteed upper limit with resistor tolerance.', '22nF dVdt: nominal 1.91V/ms, approximately 2.62ms to 5V. Check loaded startup/SOA.', 'Fault output is exposed for diagnostics; auto-retry under overload is not a validated operating mode.', 'External VBUS transient protection, shutdown discharge and complete power/load budget remain open.', 'Source: TI TPS2595 SLVSE57C equations 3/4 and electrical-characteristics table.']):fuse.note(t,20,200+i*7)
 fuse.save()
 buck=Sheet('system-3v3','Phoenix G1 - 3.3V system converter','Phoenix_InputPower',syms)
 nets={'1':'SYS_SW','2':'SYS_SW','3':'SYS_SW','4':'SYS_3V3_PG','5':'GND','6':'GND','7':'GND','8':'GND','9':'SYS_SS','10':'+5V_MAIN','11':'+5V_MAIN','12':'+5V_MAIN','13':'WIFI_VBAT_PG','14':'+3V3_SYS','15':'GND','16':'GND','17':'GND'}
 buck.place('TPS62132RGTR','U17',111.76,66.04,nets,mpn='TPS62132RGTR')
 buck.place('L','L1301',238.76,66.04,{'1':'SYS_SW','2':'+3V3_SYS'},'2.2uH DCR35m max',fp='Phoenix_Passives:L_APH0518',mpn='APH0518T2R2M')
 r(buck,'R1301',330.2,66.04,'SYS_3V3_PG','+3V3_SYS','100k')
 for i,(x,net,val,large) in enumerate([(30.48,'+5V_MAIN','10u / 10V',True),(101.6,'+5V_MAIN','100n / 10V',False),(172.72,'SYS_SS','10n / 10V',False),(243.84,'+3V3_SYS','22u / 10V',True),(314.96,'+3V3_SYS','22u / 10V',True)]):c(buck,f'C{1301+i}',x,152.4,net,val,large)
 for i,t in enumerate(['TPS62132 is the fixed 3.3V variant; TPS62133 is 5V and is not interchangeable here.', 'FSW=GND: 2.5MHz. DEF=GND: nominal output. FB=GND per fixed-voltage recommendation.', 'SS=10nF gives 5ms typical ramp. Include all PMIC input capacitors in converter stability review.', 'APH0518T2R2M C5349673: 2.2uH, Isat table 4.98A, Irms table 4.32A; hot behavior and MLCC bias unqualified.', 'PG is diagnostic only here. PMIC VCC_RTC and VCC9 must rise together from +3V3_SYS.', 'A 3A converter rating does not guarantee 3A available from USB after CPU and conversion losses.']):buck.note(t,20,211+i*7)
 buck.save()
if __name__=='__main__':main()
