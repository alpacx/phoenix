#!/usr/bin/env python3
"""Candidate rail map from datasheet names/limits, separate from sequencing qualification."""
import csv,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'migration-rk3562/review'
rows=list(csv.DictReader((R/'manufacturer-pins.csv').open()));out=[]
analog={'PMUPLL_AVDD_0V9':'VDDA0V9_PMU','PMUPLL_AVDD_1V8':'VCCA1V8_PMU','SYSPLL_AVDD_0V9':'VDDA_0V9','SYSPLL_AVDD_1V8':'VCCA_1V8','PMU_VDD_LOGIC_0V9':'VDDA0V9_PMU','USB_AVDD_0V9':'USB_AVDD_0V9','USB_AVDD_1V8':'USB_AVDD_1V8','USB_AVDD_3V3':'+3V3_IO','MULTI_PHY_AVDD_0V9':'VDDA_0V9','MULTI_PHY_AVDD_1V8':'VCCA_1V8','SARADC0_AVDD_1V8':'VCCA_1V8','SARADC1_AVDD_1V8':'VCCA_1V8'}
# Keep unused analog PHY supplies powered at their specified nominal voltage;
# disabling an interface is not assumed to permit leaving its supply floating.
analog.update({
 'MIPI_CSI_RX0_AVDD_0V9':'VDDA0V9_IMAGE','MIPI_CSI_RX1_AVDD_0V9':'VDDA0V9_IMAGE',
 'MIPI_DSI_TX/LVDS_TX_AVDD_0V9':'VDDA0V9_IMAGE',
 'MIPI_CSI_RX0_AVDD_1V8':'VCCA1V8_IMAGE','MIPI_CSI_RX1_AVDD_1V8':'VCCA1V8_IMAGE',
 'MIPI_DSI_TX/LVDS_TX_AVDD_1V8':'VCCA1V8_IMAGE','OTP_VCC_1V8':'VCCA_1V8'})
for r in rows:
 n=r['name'];net=None;basis='Datasheet Rev1.2 pin table and recommended voltage ranges; source/sequence not qualified'
 if re.match(r'^(VSS_|AVSS\d?_|.*_AVSS|TVSS$)',n):net='GND';basis='Explicit ground pin name in manufacturer table'
 elif n.startswith(('DDRPHY_VDDQ_','DDRPHY_VDDQL_')):net='+1V5_DDR'
 elif n.startswith('VDD_CPU_'):net='VDD_CPU'
 elif n.startswith('VDD_GPU_'):net='VDD_GPU'
 elif n.startswith('VDD_NPU_'):net='VDD_NPU'
 elif n.startswith('VDD_LOGIC'):net='VDD_LOGIC'
 elif n in ('PMUIO0','PMUIO1'):net='+3V3_PMU'
 elif re.match(r'^VCCIO[1-6](_\d)?$',n):net='+3V3_IO'
 elif n in analog:net=analog[n]
 if net:out.append({'ball':r['ball'],'name':n,'net':net,'basis':basis})
(R/'candidate-power-map.json').write_text(json.dumps({'status':'CANDIDATE CONNECTIONS; NOT POWER SEQUENCE/PI QUALIFICATION','reference_crosscheck':'reference/rk3562-oomwoo-reference.pdf page6 visually reviewed for nPOR/PMUIO/PLL; independent hobby reference, not manufacturer approval','pins':out,'holds':['PMIC startup values and timing, rail grouping and filter/decoupling migration','IO bank membership and voltage programming','Unused analog blocks remain supplied; LDO enable, load and sequence still require qualification','USB headroom and sustained current/power budget']},indent=2)+'\n');print(len(out),'ground/supply pins mapped')
