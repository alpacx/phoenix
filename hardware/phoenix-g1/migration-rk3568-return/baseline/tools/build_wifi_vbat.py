#!/usr/bin/env python3
"""Dedicated AP6256 VBAT draft. TI TPS62130 pinout and section9.2.
Power-good startup sequencing is not a fault-safe shutdown guarantee.
"""
from schematic_builder import *
def main():
 syms=load_symbols([],['R','C','L'])
 lib=sx.loads((ROOT/'kicad/Phoenix_InputPower.kicad_sym').read_text())
 s=copy.deepcopy(next(s for s in fields(lib,'symbol') if s[1]=='TPS62132RGTR'))
 old=s[1];s[1]='TPS62130RGTR'
 for sub in fields(s,'symbol'):sub[1]=sub[1].replace(old,s[1])
 for prop in fields(s,'property'):
  if prop[1]=='Value':prop[2]=s[1]
 expected='SW SW SW PG FB AGND FSW DEF SS/TR AVIN PVIN PVIN EN VOS PGND PGND EP'.split()
 assert {str(fields(p,'number')[0][1]):fields(p,'name')[0][1] for p in walk(s,'pin')}=={str(i+1):n for i,n in enumerate(expected)}
 syms[s[1]]=s;save_library('Phoenix_WifiVbat',syms)
 sh=Sheet('wifi-vbat-converter','Phoenix G1 - dedicated Wi-Fi VBAT converter','Phoenix_WifiVbat',syms)
 nets={'1':'WIFI_VBAT_SW','2':'WIFI_VBAT_SW','3':'WIFI_VBAT_SW','4':'WIFI_VBAT_PG','5':'WIFI_VBAT_FB','6':'GND','7':'GND','8':'GND','9':'WIFI_VBAT_SS','10':'+5V_MAIN','11':'+5V_MAIN','12':'+5V_MAIN','13':'+5V_MAIN','14':'+3V58_WIFI','15':'GND','16':'GND','17':'GND'}
 sh.place('TPS62130RGTR','U26',111.76,66.04,nets,mpn='TPS62130RGTR')
 sh.place('L','L2201',238.76,66.04,{'1':'WIFI_VBAT_SW','2':'+3V58_WIFI'},'2.2uH DCR35m max',fp='Phoenix_Passives:L_APH0518',mpn='APH0518T2R2M')
 for ref,x,y,a,b,v in [('R2201',330.2,66.04,'WIFI_VBAT_PG','+3V58_WIFI','100k'),('R2202',238.76,142.24,'+3V58_WIFI','WIFI_VBAT_FB','348k 1%'),('R2203',330.2,142.24,'WIFI_VBAT_FB','GND','100k 1%')]:
  sh.place('R',ref,x,y,{'1':a,'2':b},v,'Phoenix_Passives:R_0603_1608Metric' if ref=='R2202' else 'Phoenix_Passives:R_0402_1005Metric')
 for ref,x,y,net,v,large in [('C2201',30.48,142.24,'+5V_MAIN','10u / 10V',True),('C2202',101.6,142.24,'+5V_MAIN','100n / 16V',False),('C2203',172.72,142.24,'WIFI_VBAT_SS','1n / 10V',False),('C2204',30.48,203.2,'+3V58_WIFI','22u / 10V',True)]:
  sh.place('C',ref,x,y,{'1':net,'2':'GND'},v,'Phoenix_Passives:C_0805_2012Metric' if large else 'Phoenix_Passives:C_0402_1005Metric')
 for i,t in enumerate(['VOUT=0.8*(1+348k/100k)=3.584V. VOS senses before ferrite; include ferrite drop in VBAT margin.', '2.2uH / 22uF converter filter plus module22uF behind ferrite: combined impedance/transients require qualification.', 'PG pull-up is to its own VBAT source, not 5V: enables U17 only after nominal Wi-Fi VBAT startup.', 'TPS62130 PG floats in shutdown/UVLO/thermal shutdown; this is NOT a fail-safe power sequencer.', 'SS=1nF: 0.5ms typical. Do not infer guaranteed sequencing under faults or retained output charge.', 'Verify VIN headroom, USB total power, effective capacitors, inductor fault current and discharge before release.']):sh.note(t,15,242+i*6)
 sh.save()
if __name__=='__main__':main()
