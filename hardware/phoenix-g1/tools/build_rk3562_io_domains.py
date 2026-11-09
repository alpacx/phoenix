#!/usr/bin/env python3
"""Record externally corroborated IO bank assignments; firmware still required."""
import json,re
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'migration-rk3562/review'
a=json.loads((R/'independent-reference-check.json').read_text())
rows=[]
for c in a['checks']:
 ref=c['reference']
 if not ref:continue
 domain=ref['domain']; funcs=ref['functions']
 if domain=='PMUIO/OSC/PLL':
  gpio=next((f for f in funcs if re.fullmatch(r'GPIO0_[A-D][0-7]_[duz]',f)),None)
  if not gpio:continue
  bankbit=ord(gpio[6])-ord('A'); bit=int(gpio[7]);index=8*bankbit+bit
  domain='PMUIO0' if index<=10 else 'PMUIO1'
 elif not domain.startswith('VCCIO'):continue
 domain=domain.removesuffix(' Domain')
 rows.append({'net':c['net'],'ball':c['ball'],'domain':domain,'design_voltage_v':3.3,'design_rail':'+3V3_PMU' if domain.startswith('PMUIO') else '+3V3_IO','reference_page':ref['pdf_page'],'function_match':c['result']=='MATCH'})
report={'status':'DOCUMENTED DRAFT; BOOT AND IO VOLTAGE CONFIGURATION NOT VALIDATED','signals':rows,'requirements':['PMUIO0 is fixed 3.3V; PMUIO1 and VCCIO banks must be configured consistently with actual supplies.','Preserve voltage-compatible states during boot, suspend and power-off; inspect external pull-ups for back-power.','Pinmux and IO voltage registers/device tree must be updated for RK3562, not inherited from RK3568.'],'scope':'PMUIO split from GPIO0_A0..B2 versus GPIO0_B3..D1 in designer reference p6; VCCIO assignment from extracted symbol groups p7..11. Not independent manufacturer bank qualification.'}
(R/'io-domain-plan.json').write_text(json.dumps(report,indent=2)+'\n')
print(len(rows),'IO allocations recorded')
