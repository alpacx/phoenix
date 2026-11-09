#!/usr/bin/env python3
"""AP6256 circuit from AMPAK pin table and Radxa ROCK 3C v1.31 sheet22.
Reference values are starting points, not RF/power qualification.
"""
from schematic_builder import *
def main():
 syms=load_symbols([],['R','C','L'])
 for lib in ['Import_C5248079','Phoenix_WifiImports']:
  for s in fields(sx.loads((ROOT/f'kicad/{lib}.kicad_sym').read_text()),'symbol'):
   for p in fields(s,'property'):p[:]=[v for v in p if not(isinstance(v,list) and v and str(v[0])=='id')]
   syms[s[1]]=s
 # Imported electrical types are not trusted. NC test pads remain disconnected.
 ground={'1','3','20','31','33','36'}; power={'9','22','23'}; outputs={'7','13','25','41','42'}
 nc={'4','5','8','30','32','35','45','46','47'}
 for p in walk(syms['AP6256'],'pin'):
  num=str(fields(p,'number')[0][1])
  if num=='41':fields(p,'name')[0][1]='UART_RTS_N'
  p[1]=sx.Symbol('power_in' if num in ground|power else 'no_connect' if num in nc else 'power_out' if num=='21' else 'output' if num in outputs else 'passive' if num in {'2','10','11','21'} else 'bidirectional' if num in {'14','15','16','18','19','37','38','39','40'} else 'input')
 for name in ['OVETDLJANF-32.768KHZ','X1E0000210877','U.FL-R-SMT-1']:
  for p in walk(syms[name],'pin'):
   num=str(fields(p,'number')[0][1]);p[1]=sx.Symbol('passive' if name!='OVETDLJANF-32.768KHZ' else 'input' if num=='1' else 'output' if num=='3' else 'power_in')
 save_library('Phoenix_WifiCircuit',syms)
 p=ROOT/'kicad/fp-lib-table';t=p.read_text()
 if '(name "Phoenix_WifiImports")' not in t:p.write_text(t.rstrip()[:-1]+' (lib (name "Phoenix_WifiImports")(type "KiCad")(uri "${KIPRJMOD}/Phoenix_WifiImports.pretty")(options "")(descr "Imported crystal land pattern; qualification pending"))\n)\n')
 def r(sh,ref,x,y,a,b,v):sh.place('R',ref,x,y,{'1':a,'2':b},v,'Phoenix_Passives:R_0402_1005Metric')
 def c(sh,ref,x,y,a,v,large=False):sh.place('C',ref,x,y,{'1':a,'2':'GND'},v,'Phoenix_Passives:C_0805_2012Metric' if large else 'Phoenix_Passives:C_0402_1005Metric')
 sh=Sheet('wifi-module','Phoenix G1 - Wi-Fi SDIO and external antenna','Phoenix_WifiCircuit',syms)
 nets={str(i):None for i in range(1,48)}
 for n in ground:nets[n]='GND'
 nets.update({'2':'WIFI_RF','6':'GND','9':'WIFI_VBAT','10':'WIFI_XIN','11':'WIFI_XOUT','12':'WIFI_REG_ON','13':'WIFI_HOST_WAKE','14':'WIFI_D2','15':'WIFI_D3','16':'WIFI_CMD','17':'WIFI_CLK','18':'WIFI_D0','19':'WIFI_D1','21':'WIFI_BUCK_SW','22':'+3V3_IO','23':'WIFI_BUCK_OUT','24':'WIFI_LPO','26':'GND','27':'GND','28':'GND','29':'GND','34':'GND','43':'GND','44':'GND'})
 sh.place('AP6256','U25',101.6,106.68,nets,mpn='AP6256',fp='Phoenix_Reviewed:AP6256_12x12_P0.9')
 sh.place('U.FL-R-SMT-1','J2001',304.8,81.28,{'1':'WIFI_ANT','2':'GND','3':'GND'},mpn='U.FL-R-SMT-1(80)',fp='Phoenix_Reviewed:Hirose_UFL_R_SMT_1_80')
 r(sh,'R2001',284.48,139.7,'WIFI_RF','WIFI_ANT','0R RF tuning')
 r(sh,'R2002',284.48,200.66,'WIFI_REG_ON','GND','10k')
 for i,t in enumerate(['Bluetooth disabled: BT_REG_ON and unused BT inputs held low. No Bluetooth software support assumed.', 'SDIO_VSEL low selects 3.3V; VCCIO4 and module VDDIO must both remain at 3.3V.', 'VBAT must precede or coincide with VDDIO. REG_ON stays low until power and LPO are stable.', 'RF trace 50 ohm to U.FL; antenna and matching require measurement. No integrated antenna.', 'AP mode, firmware/NVRAM and country configuration remain software validation holds.']):sh.note(t,15,251+i*6)
 sh.save()
 sh=Sheet('wifi-power','Phoenix G1 - Wi-Fi power filtering','Phoenix_WifiCircuit',syms)
 sh.place('L','FB2001',60.96,50.8,{'1':'+3V58_WIFI','2':'WIFI_VBAT'},'100R @100MHz / 4A','Phoenix_Passives:R_0805_2012Metric',mpn='MPZ2012S101AT000')
 c(sh,'C2001',177.8,50.8,'WIFI_VBAT','22u / 6.3V',True);c(sh,'C2002',294.64,50.8,'WIFI_VBAT','100n / 16V')
 sh.place('L','L2001',60.96,121.92,{'1':'WIFI_BUCK_SW','2':'WIFI_BUCK_OUT'},'2.2uH / 2.4A Isat at 20C','Phoenix_Reviewed:Murata_DFE201610E',mpn='DFE201610E-2R2M=P2')
 c(sh,'C2003',177.8,121.92,'WIFI_BUCK_OUT','4.7u / 6.3V',True)
 for ref,x,v in [('C2004',60.96,'4.7u / 6.3V'),('C2005',177.8,'1u / 10V'),('C2006',294.64,'100n / 16V')]:c(sh,ref,x,193.04,'+3V3_IO',v)
 for i,t in enumerate(['Reference: Radxa ROCK 3C v1.31 sheet22, AP6256 internal regulator 2.2uH + 4.7uF.', 'FB2001: 4A, 20mohm max; DC margin improved, RF/transient qualification pending. L2001: 2.4A saturation / 1.7A thermal at 20C; hot/fault current unqualified.', 'VBAT peaks up to 1A. Dedicated 3.584V regulator and USB admission need complete load/transient analysis.', 'VBAT derives from dedicated3.584V converter; its PG enables system3.3V. Fault/shutdown sequencing remains unqualified.']):sh.note(t,15,251+i*6)
 sh.save()
 sh=Sheet('wifi-clocks','Phoenix G1 - Wi-Fi reference clocks','Phoenix_WifiCircuit',syms)
 sh.place('OVETDLJANF-32.768KHZ','Y2001',60.96,55.88,{'1':'+3V3_IO','2':'GND','3':'WIFI_LPO_SRC','4':'+3V3_IO'},mpn='OVETDLJANF-32.768KHZ',fp='Phoenix_Reviewed:Taitien_OV_5032')
 r(sh,'R2003',177.8,55.88,'WIFI_LPO_SRC','WIFI_LPO','22R');c(sh,'C2007',294.64,55.88,'+3V3_IO','100n')
 sh.place('X1E0000210877','Y2002',177.8,132.08,{'1':'WIFI_XIN','2':'GND','3':'WIFI_XTAL_OUT','4':'GND'},mpn='X1E0000210877')
 r(sh,'R2004',60.96,132.08,'WIFI_XOUT','WIFI_XTAL_OUT','100R')
 c(sh,'C2008',60.96,203.2,'WIFI_XIN','8p C0G');c(sh,'C2009',294.64,203.2,'WIFI_XTAL_OUT','8p C0G')
 for i,t in enumerate(['37.4MHz, CL12pF crystal; 8pF loads and 100R copied from AP6256 Radxa circuit, NOT oscillator qualified.', 'Confirm frequency, load pulling, ESR/drive margin and startup across voltage/temperature.', '32.768kHz candidate +/-25ppm; AMPAK requires +/-30ppm. Exact jitter band still needs qualification.', 'Firmware: wait at least 10ms after IO/LPO power before asserting REG_ON; validate real sequencing.']):sh.note(t,15,251+i*6)
 sh.save()
 sh=Sheet('wifi-sdio-pulls','Phoenix G1 - SDIO bus idle state','Phoenix_WifiCircuit',syms)
 for i,net in enumerate(['WIFI_D0','WIFI_D1','WIFI_D2','WIFI_D3','WIFI_CMD']):r(sh,f'R{2010+i}',60.96+(i%3)*116.84,60.96+(i//3)*76.2,net,'+3V3_IO','47k')
 sh.note('SDIO external pull-ups to matching IO rail; no pull-up on CLK. 3.3V fixed, disable 1.8V switching in DTS.',15,251)
 sh.note('Start at conservative SDIO clock; determine series termination and final rate from routed channel and measurements.',15,259)
 sh.save()
if __name__=='__main__':main()
