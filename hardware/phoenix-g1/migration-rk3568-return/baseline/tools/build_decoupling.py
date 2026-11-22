#!/usr/bin/env python3
"""Explicit distributed bypass inventory; placement and impedance remain unqualified."""
from schematic_builder import *
def main():
 syms=load_symbols([],['C','R']);save_library('Phoenix_Decoupling',syms)
 groups=[('soc-core-bypass',[
 ('VDD_CPU',['100n','4.7u']+['22u']*6),
 ('VDD_LOGIC',['100n','4.7u','1u','1u','22u','22u','10u']),
 ('VDD_GPU',['100n','4.7u','22u','22u','10u']),
 ('VDD_NPU',['100n','22u','22u','10u'])]),
 ('soc-io-bypass',[(rail,['100n','1u']) for rail in ['+3V3_PMU','+3V3_IO','VDDA0V9_PMU','VCCA1V8_PMU','VDDA_0V9','VCCA_1V8']]+[('+3V3_IO',['100n']*5),('VDDA_0V9',['100n']*2),('VCCA_1V8',['100n']*2)]),
 ('ddr-bypass',[('+1V5_DDR',['100n','100n','4.7u','4.7u','10u']),('+1V5_DDR',['100n']*12+['4.7u','10u']),('+1V5_DDR',['100n']*12+['4.7u','10u'])]),
 ('usb-analog-bypass',[('USB_AVDD_0V9',['100n','1u']),('USB_AVDD_1V8',['100n','1u']),('+3V3_IO',['100n'])])]
 idx=1600
 for name,rails in groups:
  sh=Sheet(name,'Phoenix G1 - '+name,'Phoenix_Decoupling',syms);j=0
  for group,(rail,values) in enumerate(rails):
   for value in values:
    idx+=1;x=30.48+(j%6)*63.5;y=35.56+(j//6)*35.56
    sh.place('C',f'C{idx}',x,y,{'1':rail,'2':'GND'},value+' / 10V',fp='Phoenix_Passives:C_0805_2012Metric' if value in ['10u','22u'] else 'Phoenix_Passives:C_0402_1005Metric');j+=1
  if name=='usb-analog-bypass':
   for k,(src,dst) in enumerate([('VDDA_0V9','USB_AVDD_0V9'),('VCCA_1V8','USB_AVDD_1V8')]):
    sh.place('R',f'R{1601+k}',60.96+k*152.4,137.16,{'1':src,'2':dst},'0R supply link','Phoenix_Passives:R_0402_1005Metric')
  sh.note('DRAFT: exact MLCC MPNs, effective capacitance, ESR and mounting inductance not yet qualified.',15,253)
  sh.note('CPU: six local 22uF plus four regulator 22uF = 220uF nominal, before tolerance/DC bias/temperature.',15,260)
  sh.note('DDR: first group at SoC; next groups at U2 and U3. Layout must distribute bypass by power-ball groups.',15,267)
  sh.note('Core values follow Rockchip reference; DDR per-chip allocation is provisional and requires PI review.',15,274)
  sh.save()
if __name__=='__main__':main()
