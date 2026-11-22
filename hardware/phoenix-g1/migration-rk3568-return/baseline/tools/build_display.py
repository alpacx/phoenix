#!/usr/bin/env python3
"""Display electrical draft. FPC attachment process and VDDIO relation remain release holds."""
from schematic_builder import *
def main():
 syms=load_symbols([],['R','C'])
 for code in ['C963429','C113281','C20526']:
  for s in fields(sx.loads((ROOT/f'kicad/Import_{code}.kicad_sym').read_text()),'symbol'):
   for p in fields(s,'property'):p[:]=[v for v in p if not(isinstance(v,list) and v and str(v[0])=='id')]
   syms[s[1]]=s
  p=ROOT/'kicad/fp-lib-table';text=p.read_text()
  if f'(name "Import_{code}")' not in text:p.write_text(text.rstrip()[:-1]+f' (lib (name "Import_{code}")(type "KiCad")(uri "${{KIPRJMOD}}/Import_{code}.pretty")(options "")(descr "Imported candidate; geometry review required"))\n)\n')
 display=fields(sx.loads((ROOT/'kicad/Phoenix_Display.kicad_sym').read_text()),'symbol')[0];syms[display[1]]=display
 names={'TPS7A2030PDBVR':{'1':'IN','2':'GND','3':'EN','4':'N/C','5':'OUT'},'SN74LVC541APWR_C113281':{'1':'~{OE1}',**{str(i+1):'A'+str(i) for i in range(1,9)},'10':'GND',**{str(19-i):'Y'+str(i) for i in range(1,9)},'19':'~{OE2}','20':'VCC'},'MMBT3904-C20526':{'1':'B','2':'E','3':'C'}}
 for name,mapping in names.items():
  assert mapping=={str(fields(p,'number')[0][1]):fields(p,'name')[0][1] for p in walk(syms[name],'pin')},name
  for p in walk(syms[name],'pin'):
   n=fields(p,'name')[0][1]
   p[1]=sx.Symbol('passive' if name.startswith('MMBT') else 'power_in' if n in ['GND','VCC','IN'] else 'power_out' if n=='OUT' else 'output' if n.startswith('Y') else 'no_connect' if n=='N/C' else 'input')
 save_library('Phoenix_DisplayCircuit',syms)
 def r(sh,ref,x,y,a,b,value):sh.place('R',ref,x,y,{'1':a,'2':b},value,'Phoenix_Passives:R_0402_1005Metric')
 def c(sh,ref,x,y,rail,value):sh.place('C',ref,x,y,{'1':rail,'2':'GND'},value,'Phoenix_Passives:C_0402_1005Metric')
 sh=Sheet('display-power','Phoenix G1 - display supply and backlight','Phoenix_DisplayCircuit',syms)
 sh.place('TPS7A2030PDBVR','U20',76.2,60.96,{'1':'+5V_MAIN','2':'GND','3':'+3V3_IO','4':None,'5':'+3V0_LCD'},mpn='TPS7A2030PDBVR')
 c(sh,'C1801',177.8,60.96,'+5V_MAIN','1u / 10V');c(sh,'C1802',279.4,60.96,'+3V0_LCD','2.2u / 10V')
 sh.place('MMBT3904-C20526','Q1',177.8,162.56,{'1':'LCD_BL_BASE','2':'GND','3':'LCD_LEDK'},mpn='MMBT3904(RANGE:100-300)')
 r(sh,'R1801',60.96,162.56,'LCD_BL_PWM','LCD_BL_BASE','1k')
 r(sh,'R1802',279.4,162.56,'LCD_BL_BASE','GND','47k')
 sh.place('R','R1803',60.96,223.52,{'1':'+5V_MAIN','2':'LCD_LEDA'},'180R 1%','Phoenix_Passives:R_0603_1608Metric')
 r(sh,'R1804',177.8,223.52,'+3V3_IO','GND','100k')
 for i,t in enumerate(['Display 3.0V supply enabled only with IO power; 1.5% TI accuracy fits the stated 2.5-3.3V operating range.', 'LED drive is current-limited by 180R; brightness varies with VBUS and Vf. PWM dimming; off at reset.', 'At5.9V static clamp bound, Vf=2.9V and zero VCE: <=16.84mA; resistor50.51mW. Transient overshoot excluded.', 'Nominal LED current is about 10mA; datasheet full-brightness minimum 15mA is NOT guaranteed.', 'R1804 discharges the enable rail weakly. Validate all supply fall times and no back-powering.']):sh.note(t,15,251+i*6)
 sh.save()
 sh=Sheet('display-signals','Phoenix G1 - write-only SPI display interface','Phoenix_DisplayCircuit',syms)
 inputs=['LCD_MOSI','LCD_SCLK','LCD_DC','LCD_RESET_N','LCD_CS_N'];outputs=['LCD_DIN_3V','LCD_CLK_3V','LCD_DC_3V','LCD_RST_3V','LCD_CS_3V']
 nets={'1':'GND','10':'GND','19':'GND','20':'+3V0_LCD'}
 for i in range(1,9):nets[str(i+1)]=inputs[i-1] if i<=5 else 'GND';nets[str(19-i)]=outputs[i-1] if i<=5 else None
 sh.place('SN74LVC541APWR_C113281','U21',91.44,71.12,nets,mpn='SN74LVC541APWR')
 sh.place(display[1],'DS1',279.4,71.12,{'1':None,'2':None,'3':'LCD_DIN_3V','4':'LCD_CLK_3V','5':'LCD_DC_3V','6':'LCD_RST_3V','7':'LCD_CS_3V','8':'GND','9':None,'10':'+3V0_LCD','11':'LCD_LEDK','12':'LCD_LEDA','13':'GND'},mpn='N096-1608TBBIG11-H13',fp='')
 c(sh,'C1811',35.56,162.56,'+3V0_LCD','100n');c(sh,'C1812',111.76,162.56,'+3V0_LCD','1u / 10V')
 for i,net in enumerate(inputs):r(sh,f'R{1811+i}',35.56+i*76.2,223.52,net,'+3V3_IO' if net=='LCD_CS_N' else 'GND','47k')
 for i,t in enumerate(['SN74LVC541A accepts 3.3V input while powered at 3.0V. Unused inputs grounded; unused outputs NC.', 'Display SDA is write-only in this circuit; no readback through the unidirectional buffer.', 'RELEASE HOLD: display datasheet names VDDIO but has no separate pin. Confirm internal supply relationship.', 'RELEASE HOLD: 13 contact FPC at 0.7mm pitch is not a standard 0.5mm ZIF. Attachment/footprint remain unqualified.', 'Panel body 13.5 x27.95mm plus flex. Fold radius, exposed contacts, retention and assembly method unresolved.']):sh.note(t,15,251+i*6)
 sh.save()
if __name__=='__main__':main()
