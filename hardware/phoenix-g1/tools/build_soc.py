#!/usr/bin/env python3
"""RK3568 multi-unit circuit and explicit dispositions for every ball.
Unused-pin defaults come from Rockchip's unused-pins worksheet, not guessing.
"""
import csv,re,zipfile,xml.etree.ElementTree as ET
from collections import OrderedDict
from schematic_builder import *
from build_expansion import SIGNALS as EXPANSION_SIGNALS
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def unused_rules():
 with zipfile.ZipFile(ROOT/'reference/RK3568-unused-pins.xlsx') as z:
  strings=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS)]
  result={}
  for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//m:row',NS):
   cells={}
   for c in row:
    v=c.findtext('m:v','',NS);cells[re.sub(r'\d','',c.attrib['r'])]=strings[int(v)] if c.attrib.get('t')=='s' else v
   if re.fullmatch('[A-Z]{1,2}[0-9]{1,2}',cells.get('A','')):result[cells['A']]=cells.get('C','')
  return result

def main():
 rows=list(csv.DictReader((ROOT/'review/rk3568-manufacturer-pins.csv').open()));byball={r['ball']:r for r in rows};rules=unused_rules()
 nets={};reasons={};unresolved=[]
 for r in rows:
  b=r['ball'];rule=rules.get(b,'')
  if rule=='Tie VSS':nets[b]='GND'
  elif 'Leave floating' in rule:nets[b]=None
  else:continue
  reasons[b]='Unused-pin worksheet: '+rule
 def assign(b,net,reason):
  assert b in byball,b;nets[b]=net;reasons[b]=reason
 # Active core and GPIO domains. Unused interfaces retain the manufacturer's disposition.
 for r in rows:
  b=r['ball'];n=r['name']
  for prefix in ['VDD_CPU','VDD_LOGIC','VDD_GPU','VDD_NPU']:
   if n.startswith(prefix):assign(b,prefix+'_COM' if n.endswith('_COM') else prefix,'PMIC/core rail')
  if n.startswith('DDRPHY_VDDQ'):assign(b,'+1V5_DDR','DDR3 requires both VDDQ/VDDQL at 1.5V')
  if n.startswith(('PMUIO1','PMUIO2')):assign(b,'+3V3_PMU','Always-on IO voltage 3.3V')
  if n.startswith(('VCCIO2','VCCIO3','VCCIO4','VCCIO6')):assign(b,'+3V3_IO','3.3V IO bank; DTS voltage must match')
 rails={'V21':'VDDA0V9_PMU','Y21':'VCCA1V8_PMU','P11':'VDDA_0V9','N10':'VCCA_1V8','V19':'VDDA0V9_PMU','H22':'VCCA_1V8','H20':'VCCA_1V8',
 'P22':'USB_AVDD_0V9','P23':'USB_AVDD_1V8','M23':'+3V3_IO','R20':'VDDA_0V9','R21':'VDDA_0V9','R22':'VCCA_1V8'}
 for b,n in rails.items():assign(b,n,'Active PLL/ADC/USB analog rail; filtering on decoupling sheets')
 for s in json.loads((ROOT/'review/ddr3-signal-plan.json').read_text())['signals']:
  if s['soc_ball']:assign(s['soc_ball'],s['logical_net'],'Audited DDR3 RAM interconnect')
 for b in ['B8','C5','A2','B2']:assign(b,None,'Unused DDR3 A14/A15 and second-rank CS/ODT, single-rank 2Gbit devices')
 assign('H7','DDR_RZQ','120R 1% calibration resistor required')
 direct={'AF27':'XOUT24M','AF28':'XIN24M','AH27':'RESET_N','AG28':'PMIC_SLEEP','AA22':'PMIC_INT_N','AF24':'I2C0_SCL','AB21':'I2C0_SDA','AG25':'FLASH_VOL_SEL',
 'AC20':'DEBUG_RX','AH24':'DEBUG_TX','B27':'RECOVERY_ADC','AG26':'THERMAL_SHUTDOWN',
 'T28':'SOC_USB_TX_P','T27':'SOC_USB_TX_N','R28':'SOC_USB_RX_P','R27':'SOC_USB_RX_N','P27':'USB_DP','P28':'USB_DM','M24':'SOC_VBUS_DET'}
 for b,n in direct.items():assign(b,n,'Phoenix function allocation; support circuits required')
 assign('L23',None,'UFP-only USB ID left open; force peripheral mode in software')
 # Mux selection is explicit and audited against official alternate-function strings.
 funcs={}
 for r in rows:
  for f in re.split(r'[/|]',r['name']+'|'+r['functions']):funcs[f.strip()]=r['ball']
 active={}
 for f in ['GMAC1_TXD0_M1','GMAC1_TXD1_M1','GMAC1_TXD2_M1','GMAC1_TXD3_M1','GMAC1_TXCLK_M1','GMAC1_TXEN_M1','GMAC1_RXD0_M1','GMAC1_RXD1_M1','GMAC1_RXD2_M1','GMAC1_RXD3_M1','GMAC1_RXCLK_M1','GMAC1_RXDV_CRS_M1','GMAC1_MDC_M1','GMAC1_MDIO_M1']:
  active[f]='ETH_'+f.replace('GMAC1_','').replace('_M1','')
 for f,n in [('SPI1_MOSI_M0','LCD_MOSI'),('SPI1_CLK_M0','LCD_SCLK'),('SPI1_CS0_M0','LCD_CS_N'),('PWM4','LCD_BL_PWM')]:active[f]=n
 for f,n in [('SDMMC1_D0','WIFI_D0'),('SDMMC1_D1','WIFI_D1'),('SDMMC1_D2','WIFI_D2'),('SDMMC1_D3','WIFI_D3'),('SDMMC1_CMD','WIFI_CMD'),('SDMMC1_CLK','WIFI_CLK'),('GPIO2_B1_d','WIFI_REG_ON'),('GPIO2_B2_u','WIFI_HOST_WAKE')]:active[f]=n
 # Dedicated GPIO outputs/inputs allocated on an already-powered bank.
 for f,n in [('GPIO2_C4_d','LCD_DC'),('GPIO2_C5_d','LCD_RESET_N'),('GPIO0_D3_d','ETH_RESET_GPIO_N')]:active[f]=n
 for pin,f,ball,n in EXPANSION_SIGNALS:
  assert funcs[f]==ball,(f,ball)
  active[f]=n
 for f,n in active.items():
  assert f in funcs,f
  b=funcs[f];assert b not in direct and b not in [funcs[k] for k in active if k!=f and funcs[k]==b],f
  assign(b,n,'Selected mux function '+f)
 # 3.3V quad-SPI NOR on the ROM-supported FSPI bank.
 for r in rows:
  if r['group']=='VCCIO2 Domain' and not r['name'].startswith('VCCIO'):
   assign(r['ball'],None,'Unused storage-bank alternate function')
 for b,n in {'C24':'FSPI_D0','D23':'FSPI_D1','F20':'FSPI_D2','A27':'FSPI_D3','A22':'FSPI_CLK','C23':'FSPI_CS_N'}.items():
  assert 'FSPI' in byball[b]['functions'] or 'FSPI' in byball[b]['name'],b
  assign(b,n,'Quad SPI NOR; FLASH_VOL_SEL pulled low for 3.3V')
 for r in rows:
  if r['ball'] not in nets:
   unresolved.append(r);assign(r['ball'],'UNRESOLVED_'+r['ball'],'Mandatory disposition requires review')
 # Preserve original names in the audit; display only selected/primary function to keep sheets readable.
 groups=OrderedDict()
 for r in rows:
  group=r['group'];groups.setdefault(group,[]).append(r)
 units=[]
 for name,rs in groups.items():
  for start in range(0,len(rs),56):units.append((name+(f' {start//56+1}' if len(rs)>56 else ''),rs[start:start+56]))
 name='RK3568_Phoenix';s=f'(symbol "{name}" (pin_names (offset 0.508)) (in_bom yes) (on_board yes) (property "Reference" "U" (at 0 0 0) (effects (font (size 1.27 1.27)))) (property "Value" "RK3568" (at 0 0 0) (effects (font (size 1.27 1.27)))) (property "Footprint" "Phoenix_Reviewed:BGA-636_L19.0-W19.0-P0.65-BL" (at 0 0 0) (effects (font (size 1.27 1.27)) hide)))'
 symbol=sx.loads(s)
 for i,(group,rs) in enumerate(units,1):
  # Two columns, 2.54mm pitch. Keep unit names in sheet note instead of long pin labels.
  half=(len(rs)+1)//2;height=(half+1)*2.54
  body=f'(symbol "{name}_{i}_1" (rectangle (start -43.18 {height/2}) (end 43.18 {-height/2}) (stroke (width 0) (type default)) (fill (type background))))'
  unit=sx.loads(body)
  for j,r in enumerate(rs):
   side=j>=half;idx=j-half if side else j;y=round(height/2-2.54*(idx+1),4);x=45.72 if side else -45.72;angle=180 if side else 0
   b=r['ball'];n=r['name'].split('/')[0];net=nets[b];kind='bidirectional';typ=r['type']
   if r['group'] in ('VSS','AVSS') or 'AVSS' in n or n=='TVSS':kind='power_in'
   elif typ in ('PI','API') or n.startswith(('VCCIO','DDRPHY_VDDQ','VDD_','PMUIO')) or '_AVDD_' in n:kind='power_in'
   elif typ=='PO':kind='power_out'
   elif typ in ('I','AI','CI'):kind='input'
   elif typ in ('O','AO','CO'):kind='output'
   if net and net.startswith('DDR3_'):n=net;kind='bidirectional' if 'DQ' in net and 'DM' not in net else 'output'
   if b=='AG28':kind='output'
   if b=='AF24':kind='output'
   if net and net.startswith('ETH_'):kind='bidirectional' if net=='ETH_MDIO' else ('input' if 'RX' in net else 'output')
   if n.startswith('USB3_OTG0_SSTX'):kind='output'
   if n.startswith('USB3_OTG0_SSRX'):kind='input'
   unit.append(sx.loads(f'(pin {kind} line (at {x} {y} {angle}) (length 2.54) (name {q(n)} (effects (font (size 1 1)))) (number {q(b)} (effects (font (size 1 1)))))'))
  symbol.append(unit)
 symbols={name:symbol};save_library('Phoenix_SOC',symbols)
 sheets=[]
 for start in range(0,len(units),4):
  sh=Sheet(f'soc-{start//4+1:02d}','Phoenix G1 - RK3568 ball dispositions','Phoenix_SOC',symbols)
  for j,(group,rs) in enumerate(units[start:start+4]):
   x=104.14+(j%2)*203.2;y=71.12+(j//2)*116.84
   sh.place(name,'U1',x,y,{r['ball']:nets[r['ball']] for r in rs},value='RK3568',mpn='RK3568',unit=start+j+1)
   sh.note(group,x-70,y+48.26)
  sh.note('DRAFT. Pin inventory complete; support circuits, decoupling and physical routing remain mandatory.',15,263)
  sh.note('Unused interfaces must be disabled in DTS. STORAGE_* and UNRESOLVED_* are not release-ready nets.',15,270)
  sh.save();sheets.append(sh.name)
 (ROOT/'review/soc-ball-dispositions.json').write_text(json.dumps({'status':'DRAFT, not release qualified','unresolved_count':len(unresolved),'unresolved':unresolved,'sheets':sheets,'balls':[dict(r,net=nets[r['ball']],reason=reasons[r['ball']]) for r in rows]},indent=2)+'\n')
 print('Unresolved mandatory balls:',[(r['ball'],r['name']) for r in unresolved])
if __name__=='__main__':main()
