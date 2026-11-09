#!/usr/bin/env python3
from schematic_builder import *
import shutil

def main():
 syms=load_symbols([],['R'])
 lib=sx.loads((STANDARD/'Connector.kicad_sym').read_text());syms['TestPoint']=next(s for s in fields(lib,'symbol') if s[1]=='TestPoint')
 save_library('Phoenix_Test',syms)
 fpdir=Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/TestPoint.pretty')
 fp='TestPoint_Pad_D1.0mm';shutil.copyfile(fpdir/(fp+'.kicad_mod'),ROOT/'kicad/Phoenix_Passives.pretty'/(fp+'.kicad_mod'))
 sh=Sheet('test-access','Phoenix G1 - production and recovery pads','Phoenix_Test',syms)
 nets=['GND','VBUS_RAW','+5V_MAIN','+3V3_SYS','+3V3_PMU','+3V3_IO','+1V5_DDR','VDD_CPU','RESET_N','RECOVERY_ADC','DEBUG_RX','DEBUG_TX','USB_POWER_FAULT_N','SYS_3V3_PG']
 for i,net in enumerate(nets):sh.place('TestPoint',f'TP{i+1}',35.56+(i%5)*76.2,45.72+(i//5)*60.96,{'1':net},net,'Phoenix_Passives:'+fp,mpn='PCB copper feature')
 sh.note('No external header: fixture pads only. UART 3.3V; connect ground first. Do not apply external power to rail pads.',15,258)
 sh.note('R1507 on core-boot-support implements the single TSADC reset link. Software must configure active-low shutdown before enabling it.',15,265)
 sh.note('RESET_N also restarts RK809-5. Never add a downstream supervisor that holds it low through the PMIC sequence.',15,272)
 sh.save()
 # Test points are copper features, not purchased assembly parts.
 p=ROOT/'kicad/test-access.kicad_sch';sch=sx.loads(p.read_text())
 for symbol in fields(sch,'symbol'):
  if fields(symbol,'lib_id')[0][1].endswith(':TestPoint'):fields(symbol,'in_bom')[0][1]=sx.Symbol('no')
 p.write_text(sx.dumps(sch)+'\n')
if __name__=='__main__':main()
