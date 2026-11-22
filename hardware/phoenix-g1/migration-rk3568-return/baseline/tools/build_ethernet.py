#!/usr/bin/env python3
"""Gigabit PHY circuit draft; magnetics and passive qualification remain explicit."""
from schematic_builder import *
import sexpdata as sx

def main():
 syms=load_symbols(['RTL8211F-CG','HR911130A'],['R','C','L','Crystal_GND24'])
 official='MDIP0 MDIN0 AVDD10 MDIP1 MDIN1 MDIP2 MDIN2 AVDD10 MDIP3 MDIN3 AVDD33 PHYRSTB MDC MDIO TXD3 TXD2 TXD1 TXD0 TXCTL TXC DVDD10 PHYAD0/RXD3 PLLOFF/RXD2 TXDLY/RXD1 RXDLY/RXD0 PHYAD2/RXCTL PHYAD1/RXC DVDD_RG DVDD33 REG_OUT/LDO_OUT INTB/PMEB CFG_EXT/LED0 CFG_LDO0/LED1 CFG_LDO1/LED2 CLKOUT XTAL_IN XTAL_OUT/EXT_CLK AVDD10 RSET AVDD33 GND'.split()
 assert {str(fields(p,'number')[0][1]):fields(p,'name')[0][1] for p in walk(syms['RTL8211F-CG'],'pin')}=={str(i+1):n for i,n in enumerate(official)}
 for p in walk(syms['RTL8211F-CG'],'pin'):
  num=int(fields(p,'number')[0][1]);kind='input'
  if num in [3,8,11,21,28,29,38,40,41]:kind='power_in'
  elif num==30:kind='power_out'
  elif num in [1,2,4,5,6,7,9,10,14]:kind='bidirectional'
  elif num in [22,23,24,25,26,27,32,33,34,35,37]:kind='output'
  elif num==31:kind='open_collector'
  elif num==39:kind='passive'
  p[1]=sx.Symbol(kind)
 for p in walk(syms['HR911130A'],'pin'):p[1]=sx.Symbol('passive')
 save_library('Phoenix_Ethernet',syms)
 phy=Sheet('ethernet-phy','Phoenix G1 - Gigabit Ethernet PHY','Phoenix_Ethernet',syms)
 nets={str(i):n for i,n in enumerate(['ETH_MDI0_P','ETH_MDI0_N','+1V0_PHY','ETH_MDI1_P','ETH_MDI1_N','ETH_MDI2_P','ETH_MDI2_N','+1V0_PHY','ETH_MDI3_P','ETH_MDI3_N','+3V3_PHY','PHY_RESET_N','ETH_MDC','ETH_MDIO','PHY_TXD3','PHY_TXD2','PHY_TXD1','PHY_TXD0','PHY_TXEN','PHY_TXCLK','+1V0_PHY','PHY_RXD3','PHY_RXD2','PHY_RXD1','PHY_RXD0','PHY_RXDV_CRS','PHY_RXCLK','+3V3_PHY','+3V3_PHY','PHY_SW',None,'PHY_CFG_EXT','PHY_CFG_LDO0','PHY_CFG_LDO1',None,'PHY_XIN','PHY_XOUT','+1V0_PHY','PHY_RSET','+3V3_PHY','GND'],1)}
 phy.place('RTL8211F-CG','U5',88.9,76.2,nets,mpn='RTL8211F-CG')
 def r(sh,ref,x,y,a,b,val='22R'):sh.place('R',ref,x,y,{'1':a,'2':b},val,'Phoenix_Passives:R_0402_1005Metric')
 def c(sh,ref,x,y,a,val='100n',fp='Phoenix_Passives:C_0402_1005Metric'):sh.place('C',ref,x,y,{'1':a,'2':'GND'},val,fp)
 signals=['TXD0','TXD1','TXD2','TXD3','TXEN','TXCLK','RXD0','RXD1','RXD2','RXD3','RXDV_CRS','RXCLK']
 for i,n in enumerate(signals):r(phy,f'R{501+i}',190.5+(i%3)*76.2,35.56+(i//3)*48.26,'ETH_'+n,'PHY_'+n)
 r(phy,'R513',35.56,147.32,'PHY_RSET','GND','2.49k 1%')
 r(phy,'R514',99.06,147.32,'ETH_MDIO','+3V3_PHY','1.8k')
 r(phy,'R515',35.56,208.28,'ETH_RESET_GPIO_N','PHY_RESET_N','22R')
 r(phy,'R516',99.06,208.28,'PHY_RESET_N','GND','10k')
 c(phy,'C501',152.4,208.28,'PHY_RESET_N')
 for i,t in enumerate(['RGMII at 3.3V. Place TX series resistors at SoC, RX series resistors at PHY.', 'PHY reset held low by GPIO reset state and R516; firmware must hold >=10ms then deassert.', 'PHY inserts 2ns TX and RX delay: configure phy-mode=rgmii-id; avoid adding duplicate MAC delay.', 'Timing, pad geometry, return paths and power sequencing remain to be qualified.']):phy.note(t,20,245+i*6)
 phy.save()
 support=Sheet('ethernet-support','Phoenix G1 - PHY supplies, straps and clock','Phoenix_Ethernet',syms)
 straps=[('PHY_RXD3','+3V3_PHY'),('PHY_RXCLK','GND'),('PHY_RXDV_CRS','GND'),('PHY_RXD2','GND'),('PHY_RXD1','+3V3_PHY'),('PHY_RXD0','+3V3_PHY'),('PHY_CFG_EXT','+3V3_PHY'),('PHY_CFG_LDO0','GND'),('PHY_CFG_LDO1','GND')]
 for i,(a,b) in enumerate(straps):r(support,f'R{521+i}',35.56+(i%5)*76.2,35.56+(i//5)*48.26,a,b,'4.7k')
 r(support,'R530',340.36,83.82,'+3V3_IO','+3V3_PHY','0R - power link')
 support.place('L','L501',35.56,142.24,{'1':'PHY_SW','2':'+1V0_PHY'},'2.2uH DCR39m max',fp='Phoenix_Passives:L_ANR4030',mpn='ANR4030T2R2M')
 for i,(rail,val) in enumerate([('+1V0_PHY','4.7u'),('+1V0_PHY','100n'),('+1V0_PHY','100n'),('+1V0_PHY','100n'),('+3V3_PHY','4.7u'),('+3V3_PHY','100n'),('+3V3_PHY','100n'),('+3V3_PHY','100n'),('+3V3_PHY','1u')]):c(support,f'C{511+i}',111.76+(i%4)*76.2,142.24+(i//4)*38.1,rail,val)
 support.place('Crystal_GND24','Y501',35.56,208.28,{'1':'PHY_XIN','2':'GND','3':'PHY_XOUT','4':'GND'},'25MHz CL12pF',fp='Phoenix_Passives:Crystal_3225_YXC',mpn='X322525MOB4SI')
 c(support,'C520',35.56,259.08,'PHY_XIN','20p C0G / tune')
 c(support,'C521',111.76,259.08,'PHY_XOUT','20p C0G / tune')
 support.note('Straps: address 1, external 3.3V RGMII, TX/RX delay ON, PLL-off mode OFF.',175,252)
 support.note('C9006 crystal CL12pF; 20pF assumes 2pF stray. Verify drive and frequency on prototype.',175,259)
 support.note('Each AVDD/DVDD pin needs local bypass; verify start-up and discharge against Realtek app note.',175,266)
 c(support,'C522',187.96,218.44,'+1V0_PHY','100n')
 support.save()
 mag=Sheet('ethernet-magnetics','Phoenix G1 - RJ45 magnetics interface','Phoenix_Ethernet',syms)
 jack={'P2':'ETH_MDI0_P','P3':'ETH_MDI0_N','P4':'ETH_MDI1_P','P7':'ETH_MDI1_N','P5':'ETH_MDI2_P','P6':'ETH_MDI2_N','P8':'ETH_MDI3_P','P9':'ETH_MDI3_N','P1':'ETH_CENTER_TAP','P10':'CHASSIS','SHIELD0':'CHASSIS','SHIELD1':'CHASSIS','11':None,'12':None,'13':None,'14':None}
 mag.place('HR911130A','J2',114.3,81.28,jack,mpn='HR911130A')
 c(mag,'C531',264.16,81.28,'ETH_CENTER_TAP','1u / 10V')
 for i,t in enumerate(['DRAFT MAGNETICS. HanRun HR911130A has four chip-side center taps internally connected to P1.', 'P1 is capacitively grounded; never connect this voltage-mode PHY center tap to 3.3V.', 'Qualification hold: confirm shared-center-tap configuration for the exact RTL8211F silicon/BSP.', 'HR911130C Rev B ALSO has a common P1: it is not a separate-center-tap replacement.', 'P10 carries the integrated cable-side Bob Smith capacitor return; terminate at chassis.', 'LED pins intentionally unused. Cable-side safety capacitor and isolation are inside the jack.', 'PHY-side ESD clamps are on ethernet-esd. Chassis bonding and system surge qualification remain open.', 'No fabrication release until exact magnetics compatibility, footprint and protection review pass.']):mag.note(t,20,160+i*7)
 mag.save()
if __name__=='__main__':main()
