#!/usr/bin/env python3
"""Internal Phoenix expansion interface; custom pinout, not Raspberry Pi/HAT."""
from schematic_builder import *
# This table is also checked against the independent manufacturer ball inventory.
SIGNALS=[(3,'I2C2_SDA_M1','V6','EXP_I2C_SDA'),(5,'I2C2_SCL_M1','V5','EXP_I2C_SCL'),(7,'SPI0_CLK_M0','AC22','EXP_SPI_CLK'),(9,'SPI0_MOSI_M0','AA20','EXP_SPI_MOSI'),(11,'SPI0_MISO_M0','AC21','EXP_SPI_MISO'),(13,'SPI0_CS0_M0','AD20','EXP_SPI_CS0_N'),(15,'SPI0_CS1_M0','AD21','EXP_SPI_CS1_N'),(17,'UART1_TX_M0','G27','EXP_UART_TX'),(19,'UART1_RX_M0','F28','EXP_UART_RX'),(12,'GPIO2_B6_u','F27','EXP_GPIO0'),(14,'GPIO4_C1_d','U2','EXP_GPIO1'),(16,'GPIO4_B2_d','V4','EXP_GPIO2'),(18,'GPIO4_B3_d','V1','EXP_GPIO3')]
def main():
 syms=load_symbols([],['R','C']);s=fields(sx.loads((ROOT/'kicad/Import_C3975193.kicad_sym').read_text()),'symbol')[0]
 for prop in fields(s,'property'):prop[:]=[v for v in prop if not(isinstance(v,list) and v and str(v[0])=='id')]
 for pin in walk(s,'pin'):pin[1]=sx.Symbol('passive')
 syms[s[1]]=s;save_library('Phoenix_Expansion',syms)
 p=ROOT/'kicad/fp-lib-table';t=p.read_text()
 if '(name "Import_C3975193")' not in t:p.write_text(t.rstrip()[:-1]+' (lib (name "Import_C3975193")(type "KiCad")(uri "${KIPRJMOD}/Import_C3975193.pretty")(options "")(descr "Header pitch/pad dimensions reviewed; mating height pending"))\n)\n')
 nets={'1':'+3V3_IO','2':'+5V_MAIN',**{str(n):'GND' for n in [4,6,8,10,20]},**{str(n):net for n,func,ball,net in SIGNALS}}
 sh=Sheet('expansion','Phoenix G1 - internal stacked expansion interface','Phoenix_Expansion',syms)
 sh.place(s[1],'J3',91.44,86.36,nets,mpn='PZ127-2-10-S')
 for i,net in enumerate(['EXP_I2C_SDA','EXP_I2C_SCL']):sh.place('R',f'R{2101+i}',223.52+i*101.6,60.96,{'1':net,'2':'+3V3_IO'},'4.7k','Phoenix_Passives:R_0402_1005Metric')
 for i,net in enumerate(['EXP_SPI_CS0_N','EXP_SPI_CS1_N']):sh.place('R',f'R{2103+i}',223.52+i*101.6,132.08,{'1':net,'2':'+3V3_PMU'},'47k','Phoenix_Passives:R_0402_1005Metric')
 for i,t in enumerate(['2x10, 1.27mm pitch internal header. PHOENIX CUSTOM PINOUT: NOT HAT/PMOD/ARM debug compatible.', 'All signals 3.3V only. Internal connection, power off before attaching; no hot-plug or external back-power.', 'SPI uses PMUIO2, other IO uses VCCIO4/6. Firmware must keep signals inactive until both IO rails are valid.', 'Connector 1A contact rating is NOT an available power allocation. Add-on power budget remains unassigned.', 'Top daughterboard must clear SoC heatsink, display and RF cable; standoff/mating header height pending.', 'No PCIe/USB high-speed on this connector. I2C starts at 100kHz; SPI rate depends on daughterboard loading.']):sh.note(t,15,245+i*6)
 sh.save()
 (ROOT/'review/expansion-pinout.json').write_text(json.dumps({'status':'SCHEMATIC DRAFT; no addon load or mechanical compatibility qualified','connector':'J3 / C3975193 / PZ127-2-10-S','pitch_mm':1.27,'pinout':nets,'soc_signals':[{'pin':pin,'function':func,'ball':ball,'net':net} for pin,func,ball,net in SIGNALS],'power_budget':'Not allocated. Overall USB/regulator budget must be closed before using power pins.','qualification_holds':['Exact mating header and stack height','No GPIO back-power during sequencing','Power current allocation/protection for actual addon','Signal integrity and ESD for the chosen enclosure']},indent=2)+'\n')
if __name__=='__main__':main()
