#!/usr/bin/env python3
"""Core boot support. Open qualification items are explicit, never hidden by ERC exclusions."""
from schematic_builder import *
def main(target="RK3568", flash_only=False):
 syms=load_symbols([],['R','C','Crystal_GND24'])
 imported=sx.loads((ROOT/'kicad/Import_C97522.kicad_sym').read_text())
 flash=fields(imported,'symbol')[0]
 for p in fields(flash,'property'):p[:]=[v for v in p if not(isinstance(v,list) and v and str(v[0])=='id')]
 for pin in walk(flash,'pin'):
  num=str(fields(pin,'number')[0][1]);pin[1]=sx.Symbol('power_in' if num in ['4','8'] else 'input' if num in ['1','6'] else 'passive' if num=='9' else 'bidirectional')
 syms[flash[1]]=flash
 save_library('Phoenix_CoreSupport',syms)
 def r(sh,ref,x,y,a,b,val):sh.place('R',ref,x,y,{'1':a,'2':b},val,'Phoenix_Passives:R_0402_1005Metric')
 def c(sh,ref,x,y,a,val):sh.place('C',ref,x,y,{'1':a,'2':'GND'},val,'Phoenix_Passives:C_0402_1005Metric')
 sh=Sheet('boot-flash','Phoenix G1 - 32MiB SPI NOR boot candidate','Phoenix_CoreSupport',syms)
 sh.place(flash[1],'U18',101.6,60.96,{'1':'FSPI_CS_N','2':'FSPI_D1','3':'FSPI_D2','4':'GND','5':'FSPI_D0','6':'FLASH_CLK','7':'FSPI_D3','8':'+3V3_IO','9':'GND'},mpn='W25Q256JVEIQ')
 r(sh,'R1401',213.36,60.96,'FSPI_CLK','FLASH_CLK','22R')
 for i,(x,net) in enumerate([(50.8,'FSPI_CS_N'),(132.08,'FSPI_D2'),(213.36,'FSPI_D3')]):r(sh,f'R{1402+i}',x,142.24,net,'+3V3_IO','10k')
 c(sh,'C1401',294.64,60.96,'+3V3_IO','100n');c(sh,'C1402',294.64,142.24,'+3V3_IO','1u')
 if target=='RK3568': r(sh,'R1405',50.8,208.28,'FLASH_VOL_SEL','GND','10k')
 for i,t in enumerate(['Candidate: W25Q256JVEIQ, 256Mbit = 32MiB. JLC C97522 inventory captured separately.', 'EP pad 9 grounded per Winbond technical FAQ; no exposed vias beneath its solder land.', '32MiB requires a measured Linux/rootfs image budget. No A/B update capacity is claimed.', 'Boot ROM, loader, QE bit and 4-byte addressing compatibility need validation on hardware.', 'CS pull-up follows flash VCC. Clock resistor belongs at SoC; decoupling belongs at flash.', ('FLASH_VOL_SEL=0 selects 3.3V. Do not substitute a 1.8V flash without reworking the complete bank.' if target=='RK3568' else 'RK3562: VCCIO2 supplies FSPI at 3.3V. No RK3568 FLASH_VOL_SEL strap fitted; boot IO configuration requires validation.')]):sh.note(t,20,241+i*6)
 sh.save()
 if flash_only: return
 sh=Sheet('core-boot-support','Phoenix G1 - oscillator, recovery and calibration','Phoenix_CoreSupport',syms)
 sh.place('Crystal_GND24','Y1',101.6,60.96,{'1':'XIN24M','2':'GND','3':'XTAL24_DRIVE','4':'GND'},'24MHz CL12pF ESR40R',fp='Phoenix_Passives:Crystal_3225_JWT',mpn='CF4024M00012T8188040')
 r(sh,'R1501',223.52,60.96,'XOUT24M','XTAL24_DRIVE','22R')
 r(sh,'R1502',325.12,60.96,'XOUT24M','XIN24M','1M')
 c(sh,'C1501',50.8,137.16,'XIN24M','20p C0G / tune');c(sh,'C1502',132.08,137.16,'XTAL24_DRIVE','20p C0G / tune')
 r(sh,'R1503',223.52,137.16,'DDR_RZQ','GND','120R 1%')
 r(sh,'R1504',325.12,137.16,'RECOVERY_ADC','VCCA_1V8','10k')
 r(sh,'R1505',50.8,208.28,'+3V3_IO','SOC_VBUS_DET','100k 1%')
 r(sh,'R1506',152.4,208.28,'SOC_VBUS_DET','GND','1M 1%')
 c(sh,'C1503',254,208.28,'SOC_VBUS_DET','100n')
 r(sh,'R1507',355.6,208.28,'THERMAL_SHUTDOWN','RESET_N','0R')
 for i,t in enumerate(['VBUS detect derives from USB-powered IO rail: 3.0V nominal; only valid for this single-source UFP topology.', 'JLC C2933041: 24MHz, CL12pF, ESR40R. 20pF assumes 2pF stray; frequency/drive require prototype tuning.', 'Recovery test point must ground RECOVERY_ADC during boot. UART is 3.3V logic, never RS232.', 'TSADC_SHUT_M0 to RESET_N via R1507=0R, per Rockchip guide Figure2-3. DTS must select active-low shutdown.', 'No external 32kHz crystal: PMIC internal RC selected; RTC accuracy is not specified.']):sh.note(t,20,247+i*6)
 sh.save()
if __name__=='__main__':main()
