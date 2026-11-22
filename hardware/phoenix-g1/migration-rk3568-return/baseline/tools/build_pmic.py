#!/usr/bin/env python3
"""RK809-5 reference-derived power circuit. Passives remain procurement candidates."""
import sexpdata as sx
from schematic_builder import *

def main():
 symbols=load_symbols(['RK809-5'],['R','C','L'])
 names='SCL SDA LDO7 VCC7 LDO8 LDO9 INT FB2 SW2 VCC2 VCC1 SW1 FB1 LRCLK BCLK MCLK SDI SDO/PDMDATA PDMCLK LDO3 LDO2 VCC5 LDO1 VCC3 SW3 VBUCK3 FB3 LDO4 LDO5 VCC6 LDO6 SPKP_OUT VCC_SPK_HP SPKN_OUT VCC_CPVSS CPN CPP VCC_CPVDD HPL_OUT HP_SNS HPR_OUT MICIN MICIP VCC_1P8A VCC_RTC VREF GNDREF VCC_1P8D SLEEP XIN XOUT PWRON SW5 VCC9 SWOUT1 BATDIV VCC8 SWOUT2 FB5 EXT_EN VDC SNSP SNSN FB4 SW4 VCC4 RESETB CLK32K EP'.split()
 official={str(i+1):n for i,n in enumerate(names)}
 imported={str(fields(p,'number')[0][1]):fields(p,'name')[0][1] for p in walk(symbols['RK809-5'],'pin')}
 assert imported==official,'RK809 Rev2.3 pp18-19 pin table mismatch'
 for p in walk(symbols['RK809-5'],'pin'):
  n=fields(p,'name')[0][1];kind='input'
  if n in ['VCC'+str(i) for i in range(1,10)]+['VCC_RTC','VCC_SPK_HP','EP','GNDREF']:kind='power_in'
  elif n.startswith('LDO') or n in ['SW1','SW2','SW3','SW4','SW5','SWOUT1','SWOUT2','VREF','VCC_1P8A','VCC_1P8D']:kind='power_out'
  elif n in ['RESETB','INT','CLK32K']:kind='open_collector'
  elif n in ['SDA']:kind='bidirectional'
  elif n in ['EXT_EN','XOUT','SDO/PDMDATA','SPKP_OUT','SPKN_OUT','HPL_OUT','HPR_OUT']:kind='output'
  elif n in ['VCC_CPVSS','CPN','CPP','VCC_CPVDD']:kind='passive'
  p[1]=sx.Symbol(kind)
 save_library('Phoenix_PMIC',symbols)
 ctrl=Sheet('pmic-control','Phoenix G1 - RK809-5 control and sequencing','Phoenix_PMIC',symbols)
 mapping={'SCL':'PMIC_SCL','SDA':'PMIC_SDA','INT':'PMIC_INT_N','SLEEP':'PMIC_SLEEP','RESETB':'RESET_N','PWRON':'PMIC_PWRON_N','VDC':'PMIC_VDC',
 'VREF':'PMIC_VREF','VCC_1P8A':'PMIC_1V8A','VCC_1P8D':'PMIC_1V8D','VCC_RTC':'+3V3_SYS','VCC_SPK_HP':'+3V3_SYS',
 'VBUCK3':'+1V5_DDR','FB3':'DDR_FB','FB1':'VDD_LOGIC_COM','FB2':'VDD_GPU_COM','FB4':'VDD_NPU_COM','FB5':'+1V8_SYS',
 'LDO1':'VDDA0V9_IMAGE','LDO2':'VDDA_0V9','LDO3':'VDDA0V9_PMU','LDO4':'VCCIO_ACODEC','LDO5':'VCCIO_SD','LDO6':'+3V3_PMU','LDO7':'VCCA_1V8','LDO8':'VCCA1V8_PMU','LDO9':'VCCA1V8_IMAGE','SWOUT1':'+3V3_IO','SWOUT2':'+3V3_SD'}
 for i in range(1,10):mapping['VCC'+str(i)]='+3V3_SYS'
 for i in range(1,6):mapping['SW'+str(i)]='PMIC_SW'+str(i)
 for n in ['GNDREF','EP','BATDIV','SNSP','SNSN','LRCLK','BCLK','MCLK','SDI','PDMCLK','HP_SNS']:mapping[n]='GND'
 for n in ['SDO/PDMDATA','CPN','CPP','VCC_CPVDD','VCC_CPVSS','HPL_OUT','HPR_OUT','SPKN_OUT','SPKP_OUT','MICIP','MICIN','XIN','XOUT','CLK32K','EXT_EN']:mapping[n]=None
 assert set(mapping)==set(names)
 ctrl.place('RK809-5','U4',114.3,88.9,{p:mapping[n] for p,n in official.items()},mpn='RK809-5')
 def r(sheet,ref,x,y,a,b,val):sheet.place('R',ref,x,y,{'1':a,'2':b},val,'Phoenix_Passives:R_0402_1005Metric')
 def c(sheet,ref,x,y,a,b,val,large=False):sheet.place('C',ref,x,y,{'1':a,'2':b},val,'Phoenix_Passives:C_0805_2012Metric' if large else 'Phoenix_Passives:C_0402_1005Metric')
 # External 3.3V is supplied before PMIC: VDC divider is 1.18V nominal.
 for ref,x,y,a,b,val in [('R410',228.6,45.72,'+3V3_SYS','PMIC_VDC','180k 1%'),('R411',294.64,45.72,'PMIC_VDC','GND','100k 1%'),('R412',228.6,91.44,'+3V3_PMU','RESET_N','10k'),('R413',294.64,91.44,'+3V3_PMU','PMIC_INT_N','10k'),('R414',228.6,137.16,'I2C0_SCL','PMIC_SCL','22R'),('R415',294.64,137.16,'I2C0_SDA','PMIC_SDA','22R'),('R416',228.6,182.88,'+3V3_PMU','I2C0_SCL','2.2k'),('R417',294.64,182.88,'+3V3_PMU','I2C0_SDA','2.2k')]:r(ctrl,ref,x,y,a,b,val)
 for ref,x,y,net,val in [('C410',45.72,177.8,'PMIC_VDC','100n'),('C411',101.6,177.8,'RESET_N','100n'),('C412',157.48,177.8,'PMIC_PWRON_N','100n'),('C413',45.72,223.52,'PMIC_VREF','1u'),('C414',101.6,223.52,'PMIC_1V8A','1u'),('C415',157.48,223.52,'PMIC_1V8D','1u')]:c(ctrl,ref,x,y,net,'GND',val)
 for i,t in enumerate(['DRAFT: RK809-5 ONLY. VCC_RTC and VCC9 supplied together from +3V3_SYS.', 'Internal RC oscillator used; no accurate RTC or timed wakeup promised (datasheet 4.4.6).', 'Audio unused pins grounded/open per RK3568 reference p22. Audio supply retained at 3.3V.', 'PMIC_SLEEP needs defined SoC reset-state behavior. VDC edge startup must be bench verified.', 'No current-qualified USB input or upstream 3.3V regulator is included on this sheet.']):ctrl.note(t,205,215+i*6)
 ctrl.save()
 buck=Sheet('pmic-bucks','Phoenix G1 - PMIC switching supplies','Phoenix_PMIC',symbols)
 for i,(rail,fb) in enumerate([('VDD_LOGIC','VDD_LOGIC_COM'),('VDD_GPU','VDD_GPU_COM'),('+1V5_DDR','DDR_FB'),('VDD_NPU','VDD_NPU_COM'),('+1V8_SYS','+1V8_SYS')],1):
  yy=30.48+(i-1)*43.18
  # Inductor geometry and exact MPN intentionally unset until stock/Isat reviewed.
  buck.place('L',f'L40{i}',88.9,yy,{'1':'PMIC_SW'+str(i),'2':rail},'470nH',fp='Phoenix_Passives:L_APH201610',mpn='APH201610TR47M')
  c(buck,f'C42{i}',30.48,yy,'+3V3_SYS','GND','22u / 10V',True)
  c(buck,f'C43{i}',147.32,yy,rail,'GND','22u / 10V',True)
  c(buck,f'C44{i}',205.74,yy,rail,'GND','22u / 10V',True)
  if i in (1,2,4):
   r(buck,f'R42{i}',264.16,yy,rail,fb,'100R')
   c(buck,f'C45{i}',330.2,yy,rail,fb,'100n')
  if i==3:
   buck.place('R','R431',264.16,yy,{'1':rail,'2':fb},'105k 0.1%','Phoenix_Passives:R_0603_1608Metric',mpn='RT0603BRD07105KL')
   buck.place('R','R432',330.2,yy,{'1':fb,'2':'GND'},'120k 0.1%','Phoenix_Passives:R_0603_1608Metric',mpn='RT0603BRD07120KL')
 for i,t in enumerate(['DRAFT. Each local input capacitor belongs beside the corresponding PMIC VCC/SW pair.', 'DDR feedback targets 1.500V. Static min/max 1.4686/1.5314V; thermal drift and transients not included.', 'Output capacitors are nominal values: qualify effective capacitance under DC bias before release.', 'BUCK4/NPU defaults off; GPU retained powered for initial bring-up. Software must match RK809-5 defaults.', 'Remote-sense nodes must route to the SoC rails, separate from switching paths.', '470nH APH201610TR47M C5349593: 85C maximum INCLUDING self-heating. Thermal screening required.']):buck.note(t,20,238+i*6)
 buck.save()
 ldo=Sheet('pmic-ldos','Phoenix G1 - PMIC linear supplies and bypass','Phoenix_PMIC',symbols)
 rails=['VDDA0V9_IMAGE','VDDA_0V9','VDDA0V9_PMU','VCCIO_ACODEC','VCCIO_SD','+3V3_PMU','VCCA_1V8','VCCA1V8_PMU','VCCA1V8_IMAGE','+3V3_SD','+3V3_IO']
 for i,rail in enumerate(rails):c(ldo,f'C{460+i}',40.64+(i%4)*91.44,40.64+(i//4)*53.34,rail,'GND','10u / 10V' if rail=='+3V3_IO' else '1u / 10V',rail=='+3V3_IO')
 for i,source in enumerate(['VCC5','VCC6','VCC7','VCC8','VCC_RTC','VCC_SPK_HP']):c(ldo,f'C{480+i}',40.64+(i%4)*91.44,200.66+(i//4)*43.18,'+3V3_SYS','GND','1u / 10V')
 ldo.note('C480..C485 belong locally at VCC5, VCC6, VCC7, VCC8, VCC_RTC, VCC_SPK_HP respectively.',20,271)
 ldo.note('DRAFT: disabled output domains retained with bypass capacitors; full rail/load budget remains open.',20,278)
 ldo.save()
if __name__=='__main__':main()
