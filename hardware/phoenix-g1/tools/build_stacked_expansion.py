#!/usr/bin/env python3
"""Whole-system expansion candidate; source LPDDR4 checkpoint is preserved."""
import json,shutil,math,uuid
from pathlib import Path
import sexpdata as sx
import schematic_builder as sb
import integrate_schematic as integration
from audit_rk3568 import fields,walk
R=Path(__file__).resolve().parents[1];BASE=R/'migration-rk3562/experiments/lpddr4-1gb';OUT=R/'migration-rk3562/experiments/stacked-expansion';SYS=OUT/'system'
NETS={str(i):'+5V_ADDON' for i in range(1,9)}
NETS.update({str(i):'GND' for i in [*range(9,19),20,22,37,38]})
NETS.update(dict(zip(map(str,[19,21,23,24,25,26,27,28,29,30,31,32,33,34,35,36,39,40]),['ADDON_USB_DP','ADDON_USB_DM','EXP_I2C_SDA','EXP_I2C_SCL','EXP_UART_TX','EXP_UART_RX','EXP_GPIO0','EXP_GPIO1','EXP_GPIO2','EXP_GPIO3','EXP_SPI_CLK','EXP_SPI_MOSI','EXP_SPI_MISO','EXP_SPI_CS0_N','EXP_SPI_CS1_N','+3V3_IO',None,None])))
assert len(NETS)==40

def main():
 for folder in ['kicad','review','sourcing']:
  shutil.copytree(BASE/'system'/folder,SYS/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('pcb','integrated','*.kicad_prl','*.lck'))
 name='DF40C_40DP_DRAFT';fp='Phoenix_Stacked:DF40C_40DP_0.4V'
 symbol=f'(symbol "{name}" (pin_names(offset 0.5))(in_bom yes)(on_board yes)(property "Reference" "J" (at 0 0 0)(effects(font(size 1 1))))(property "Value" "DF40C-40DP-0.4V(51)"(at 0 0 0)(effects(font(size 1 1))))(property "Footprint" "{fp}"(at 0 0 0)(effects(font(size 1 1)) hide))(symbol "{name}_1_1"(rectangle(start -15 3)(end 15 -103)(stroke(width 0.254)(type default))(fill(type background)))'
 for n in range(1,41):symbol+=f'(pin passive line(at -17.78 {-(n-1)*2.54} 0)(length 2.54)(name "{n}"(effects(font(size 1 1))))(number "{n}"(effects(font(size 1 1)))))'
 symbol+='))'
 sb.ROOT=SYS;syms=sb.load_symbols([],['R','C']);syms[name]=sx.loads(symbol);sb.save_library('Phoenix_Stacked',syms)
 sh=sb.Sheet('expansion','Phoenix stacked accessory - replaces J3 2x10','Phoenix_Stacked',syms)
 sh.place(name,'J3',91.44,45.72,NETS,mpn='DF40C-40DP-0.4V(51)')
 for i,net in enumerate(['EXP_I2C_SDA','EXP_I2C_SCL','EXP_SPI_CS0_N','EXP_SPI_CS1_N']):
  sh.place('R',str(2101+i).join(['R','']),203.2+(i%2)*76.2,60.96+(i//2)*76.2,{'1':net,'2':'+3V3_IO' if i<2 else '+3V3_PMU'},value='4.7k' if i<2 else '47k',fp='Phoenix_Passives:R_0402_1005Metric')
 for i,t in enumerate(['J3 replaces the legacy 2x10, no additional expansion connector.', 'PHOENIX CUSTOM PINOUT. 40 contacts, USB2 host only; USB-C device stays separate.', 'GPIO0 enables power; GPIO1 fault input; GPIO2/3 accessory controls.', '3.3V logic, daughterboard provides modem level shifting. No direct SIM signals.', 'Attach only without power. Connector NOT polarized: asymmetric mechanical key required.', '8 power contacts at 0.3A each is not a 2.4A guaranteed system power budget.', '3.5mm mated spacing; addon envelope, standoffs and passive cooling NOT qualified.']):sh.note(t,20,190+8*i)
 sh.save()
 # Board land pattern from Hirose DF40 catalog page10. Numbering is Phoenix-defined.
 pretty=SYS/'kicad/Phoenix_Stacked.pretty';pretty.mkdir(exist_ok=True)
 f='(footprint "DF40C_40DP_0.4V"(version 20241229)(generator "pcbnew")(layer "F.Cu")(attr smd)'
 for layer,x,y in [('F.Fab',4.76,1.485),('F.CrtYd',5.05,1.95)]:f+=f'(fp_rect(start {-x} {-y})(end {x} {y})(stroke(width 0.05)(type default))(fill none)(layer "{layer}"))'
 f+='(fp_text user "1"(at -5.5 0)(layer "F.SilkS")(effects(font(size .8 .8)(thickness .12))))'
 for i in range(20):
  for offset,y in [(1,-1.355),(2,1.355)]:f+=f'(pad "{2*i+offset}" smd rect(at {round(-3.8+i*.4,4)} {y})(size .23 .66)(layers "F.Cu" "F.Paste" "F.Mask"))'
 for i,(x,y) in enumerate([(x,y) for x in [-4.275,4.275] for y in [-1.355,1.355]],1):f+=f'(pad "MP{i}" smd rect(at {x} {y})(size .35 .66)(layers "F.Cu" "F.Paste" "F.Mask"))'
 (pretty/'DF40C_40DP_0.4V.kicad_mod').write_text(f+')\n')
 p=SYS/'kicad/fp-lib-table';tree=sx.loads(p.read_text());tree.append(sx.loads('(lib(name "Phoenix_Stacked")(type "KiCad")(uri "${KIPRJMOD}/Phoenix_Stacked.pretty")(options "")(descr "Draft connector"))'));p.write_text(sx.dumps(tree)+'\n')
 # Activate dedicated, previously NC USB host pins, leaving USB-C OTG untouched.
 sch=SYS/'kicad/rk3562-pins-03.kicad_sch';tree=sx.loads(sch.read_text());inst=next(s for s in fields(tree,'symbol') if any(p[1]=='Reference' and p[2]=='U1' for p in fields(s,'property')));unit=fields(inst,'unit')[0][1];ix,iy=fields(inst,'at')[0][1:3]
 lib=next(s for group in fields(tree,'lib_symbols') for s in fields(group,'symbol') if s[1]==fields(inst,'lib_id')[0][1])
 for ball,net in [('AE26','ADDON_USB_DM'),('AE27','ADDON_USB_DP')]:
  pin=next(p for sub in fields(lib,'symbol') if str(sub[1]).endswith(f'_{unit}_1') for p in walk(sub,'pin') if str(fields(p,'number')[0][1])==ball)
  pin[1]=sx.Symbol('bidirectional');px,py,a=fields(pin,'at')[0][1:];x=round(ix+px,4);y=round(iy-py,4);ex=round(x-5.08*math.cos(math.radians(a)),4)
  nc=next(n for n in fields(tree,'no_connect') if fields(n,'at')[0][1:3]==[x,y]);tree.remove(nc)
  for typ,val in [('wire',f'(wire(pts(xy {x} {y})(xy {ex} {y}))(stroke(width 0)(type default))(uuid "{uuid.uuid5(uuid.NAMESPACE_URL,net+"wire")}"))'),('label',f'(label "{net}"(at {ex} {y} 0)(effects(font(size 1 1))(justify {"right" if a==0 else "left"} bottom))(uuid "{uuid.uuid5(uuid.NAMESPACE_URL,net+"label")}"))')]:tree.append(sx.loads(val))
 sch.write_text(sx.dumps(tree)+'\n');p=SYS/'review/rk3562-pins-03-expected.json';rows=json.loads(p.read_text())
 for r in rows:
  if r['ref']=='U1' and r['pin'] in ['AE26','AE27']:r['net']={'AE26':'ADDON_USB_DM','AE27':'ADDON_USB_DP'}[r['pin']]
 p.write_text(json.dumps(rows,indent=2)+'\n')
 # Protected accessory branch, default off. No load budget claimed.
 syms=sb.load_symbols([],['R','C']);lib=sx.loads((SYS/'kicad/Phoenix_InputPower.kicad_sym').read_text());s=next(s for s in fields(lib,'symbol') if s[1]=='TPS259531DSGR');syms[s[1]]=s;sb.save_library('Phoenix_AddonPower',syms)
 power=sb.Sheet('expansion-power','Phoenix accessory power - default off, current limited draft','Phoenix_AddonPower',syms)
 power.place('TPS259531DSGR','U8101',91.44,60.96,{'1':'ADDON_DVDT','2':'EXP_GPIO0','3':'+5V_MAIN','4':'+5V_MAIN','5':'+5V_ADDON','6':'EXP_GPIO1','7':'ADDON_ILIM','8':'GND','9':'GND'},mpn='TPS259531DSGR')
 for i,(a,b,v) in enumerate([('ADDON_ILIM','GND','2.1k 1% candidate'),('EXP_GPIO1','+3V3_IO','100k'),('EXP_GPIO0','GND','100k')]):power.place('R',f'R{8101+i}',203.2+i*60.96,60.96,{'1':a,'2':b},value=v,fp='Phoenix_Passives:R_0402_1005Metric')
 for i,(net,val) in enumerate([('+5V_MAIN','1u'),('+5V_ADDON','1u'),('ADDON_DVDT','22n')]):power.place('C',f'C{8101+i}',60.96+i*101.6,152.4,{'1':net,'2':'GND'},value=val,fp='Phoenix_Passives:C_0402_1005Metric')
 for i,t in enumerate(['Default OFF with 100k EN pulldown. GPIO0 must remain low until budget validated.', '2.1k ILM: 2000/R +0.04 = 0.992A nominal; tolerance/dynamics require qualification.', '1A here is a provisional branch limit, NOT an allocated modem load or promised LTE support.', 'Upstream USB eFuse nominal 2.52A also supplies the complete base board.', 'No external back-power or hot-plug permitted. Modem-specific regulation/level shifting on accessory.', 'Support MPNs, peak current, thermal, reverse current and sequencing remain qualification holds.']):power.note(t,20,205+i*8)
 power.save()
 # Prevent previous BOM selection from overwriting J3's new MPN.
 p=SYS/'sourcing/selected-references.json';sel=json.loads(p.read_text())
 for code in list(sel):
  sel[code]=' '.join(r for r in sel[code].split() if r!='J3')
  if not sel[code]:del sel[code]
 sel['C424643']='J3';p.write_text(json.dumps(sel,indent=2)+'\n')
 p=SYS/'sourcing/selected-main-parts.json';parts=json.loads(p.read_text());parts['parts'].append({'jlc':'C424643','mpn':'DF40C-40DP-0.4V(51)'});p.write_text(json.dumps(parts,indent=2)+'\n')
 integration.ROOT=SYS;integration.main()
 (OUT/'pinout.json').write_text(json.dumps({'connector':'DF40C-40DP-0.4V(51)','mate':'DF40HC(3.5)-40DS-0.4V(51)','custom_numbering':'Top view: odd row y=-1.355, even row y=+1.355, increasing left to right. Daughterboard MUST mirror mating orientation, not copy footprint net order blindly.','pins':NETS,'mounting_pads':'MP1..MP4 mechanical only, no signal or power','mated_height_mm':3.5,'assembly_ready':False},indent=2)+'\n')
if __name__=='__main__':main()
