#!/usr/bin/env python3
"""Check thermal/watchdog reset topology against Rockchip guide fig2-3."""
from pathlib import Path
import json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
x=ET.parse(ROOT/'review/integrated.xml');nets={};comps={c.get('ref'):c for c in x.findall('.//components/comp')}
for n in x.findall('.//nets/net'):
 for p in n.findall('node'):nets[p.get('ref'),p.get('pin')]=n.get('name')
assert nets['U1','AG26']==nets['R1507','1']=='THERMAL_SHUTDOWN'
assert nets['R1507','2']==nets['U1','AH27']==nets['U4','67']=='RESET_N'
assert comps['R1507'].findtext('value')=='0R'
assert {nets['C411','1'],nets['C411','2']}=={'RESET_N','GND'}
assert comps['C411'].findtext('value')=='100n'
assert {nets['R412','1'],nets['R412','2']}=={'RESET_N','+3V3_PMU'}
r={'status':'PASS DOCUMENTED RESET TOPOLOGY; not functional validation','source':'reference/Rockchip_RK3568_Hardware_Design_Guide_EN_V1.2_20220126_.pdf PDFp25-26, printed6-7','path':'RK3568 AG26 -> R1507 0R -> RESET_N -> RK3568 AH27 and RK809 pin67','reset_filter':'C411 100nF; pull-up R412 10k to matching PMUIO1 supply','firmware_holds':['Configure TSADC_SHUT_M0 and active-low polarity; never use AG26 as arbitrary GPIO.','Configure external GPIO shutdown path, thresholds and watchdog reset as required by chosen BSP.','Test PMIC restart sequencing and reset pulse >=100 main-clock periods.','Thermal shutdown is a last resort; heatsink and cooling remain unqualified.']}
(ROOT/'review/reset-path-check.json').write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
