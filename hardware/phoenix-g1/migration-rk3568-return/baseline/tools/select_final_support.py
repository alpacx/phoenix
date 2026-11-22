#!/usr/bin/env python3
"""Explicit remaining support candidates; current, RF and thermal checks stay separate."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
choices={
 'C17168':('0402WGF0000TCE','0402',['0Ω'],{'R1507':'0R','R530':'0R - power link','R1601':'0R supply link','R1602':'0R supply link','R2001':'0R RF tuning'}),
 'C185338':('RC0603FR-0733K2L','0603',['33.2kΩ','±1%','±100ppm/℃'],{'R1905':'33.2k 1%'}),
 'C273746':('RC0603FR-07348KL','0603',['348kΩ','±1%','±100ppm/℃'],{'R2202':'348k 1%'}),
}
x=ET.parse(ROOT/'review/integrated.xml');components={c.get('ref'):c for c in x.findall('.//components/comp')}
p=ROOT/'sourcing/selected-references.json';selected=json.loads(p.read_text());evidence=[]
for code,(mpn,package,specs,refs) in choices.items():
 public=json.loads((ROOT/f'sourcing/public/{code}.json').read_text())
 assert public['canPresaleNumber']>0
 assert public['componentModelEn']==mpn and public['componentSpecificationEn']==package
 assert all(s in public['describe'].split() for s in specs)
 for ref,value in refs.items():
  c=components[ref];assert c.findtext('value')==value,(ref,c.findtext('value'))
  assert c.findtext('footprint')=='Phoenix_Passives:R_'+('0402_1005Metric' if package=='0402' else '0603_1608Metric'),ref
  assert not any(ref in v.split() for k,v in selected.items() if k!=code)
 selected[code]=' '.join(refs)
 evidence.append({'jlc':code,'refs':list(refs),'evidence':f'sourcing/public/{code}.json'})
p.write_text(json.dumps(selected,indent=2)+'\n')
(ROOT/'review/final-support-selection.json').write_text(json.dumps({'status':'CANDIDATES; NOT CIRCUIT QUALIFICATION','choices':evidence,'zero_link':{'source':'reference/zero-link-C17168.pdf','revision':'2019-02-12 V3, page5 visually inspected','resistance_max_ohm':0.05,'rated_current_a':1,'overload_current_a':2,'derating_starts_c':70,'limits':['Do not treat overload rating as continuous current.','Rail current, voltage drop and hot derating remain to be qualified.','R2001 is a prototype RF matching link; no RF impedance claim.','Generic catalog percent/TCR fields for zero-ohm links were not used as resistance accuracy.']},'precision_note':'R1905 and R2202 remain1%100ppm; existing static checks do not include all temperature drift.'},indent=2)+'\n')
print('Selected',sum(len(v[-1]) for v in choices.values()),'support positions')
