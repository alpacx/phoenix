#!/usr/bin/env python3
"""Select exact-value precision candidates from saved public catalog evidence."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
choices={
 'C705762':('RT0603BRD07300KL','0603','300kΩ','300k 0.1% 25ppm',['R601','R605','R606']),
 'C190095':('RT0402BRD0710KL','0402','10kΩ','10k 0.1% 25ppm',['R1902','R1904']),
 'C861344':('RT0603BRD0735K7L','0603','35.7kΩ','35.7k 0.1% 25ppm',['R1901']),
 'C136962':('RT0603BRD0747K5L','0603','47.5kΩ','47.5k 0.1% 25ppm',['R1903']),
 'C861567':('RT0603BRD07806RL','0603','806Ω','806R 1%',['R1201']),
}
components={c.get('ref'):c for c in ET.parse(ROOT/'review/integrated.xml').findall('.//components/comp')}
p=ROOT/'sourcing/selected-references.json';selected=json.loads(p.read_text());records=[]
for code,(mpn,package,ohms,value,refs) in choices.items():
 public=json.loads((ROOT/f'sourcing/public/{code}.json').read_text())
 assert public['canPresaleNumber']>0
 assert public['componentModelEn']==mpn
 assert public['componentSpecificationEn']==package
 assert all(s in public['describe'].split() for s in [ohms,'±0.1%','±25ppm/℃'])
 footprint='Phoenix_Passives:R_'+('0402_1005Metric' if package=='0402' else '0603_1608Metric')
 for ref in refs:
  c=components[ref];assert c.findtext('value')==value,(ref,c.findtext('value'))
  assert c.findtext('footprint')==footprint,ref
  assert not any(ref in existing.split() for other,existing in selected.items() if other!=code)
 selected[code]=' '.join(refs)
 records.append({'jlc':code,'refs':refs,'evidence':f'sourcing/public/{code}.json','schematic_value':value,'actual_tolerance_percent':0.1,'actual_tcr_ppm_max':25})
p.write_text(json.dumps(selected,indent=2)+'\n')
(ROOT/'review/precision-resistors-selection.json').write_text(json.dumps({'status':'CATALOG CANDIDATES - circuit qualification remains open','choices':records,'limits':['Catalog stock is not reserved assembly inventory.','Tolerance, temperature drift and divider leakage must be included in rail bounds.','R1201 retains conservative 1% circuit analysis; selected candidate is 0.1%.']},indent=2)+'\n')
print('Selected precision positions:',sum(len(v[-1]) for v in choices.values()))
