#!/usr/bin/env python3
"""Explicit catalog selection, preserving voltage and dielectric requirements.
Not a DC-bias, effective capacitance, temperature or stability qualification.
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
choices={
 'C3849295': ('8p C0G', ['C2008','C2009'], ['8pF','50V','C0G']),
 'C1779': ('4.7u / 6.3V', ['C2003'], ['4.7uF','25V','X5R','±10%']),
 'C376925': ('1u / 25V X7R', ['C1901','C1902'], ['1uF','25V','X7R','±10%']),
 'C1554': ('20p C0G / tune', ['C1501','C1502','C520','C521'], ['20pF','50V','C0G','±5%']),
 'C1523': ('1n / 10V', ['C2203'], ['1nF','50V','X7R','±10%']),
 'C15195': ('10n / 10V', ['C1303'], ['10nF','50V','X7R','±10%']),
 'C1532': ('22n / 10V', ['C1202'], ['22nF','50V','X7R','±10%']),
 'C326606': ('2.2u / 10V', ['C1802','C1102'], ['2.2uF','10V','X5R','±10%']),
 'C53547': ('1n / C0G', ['C401','C402','C1903'], ['1nF','50V','C0G','±5%']),
}
components={c.get('ref'):c for c in ET.parse(ROOT/'review/integrated.xml').findall('.//components/comp')}
p=ROOT/'sourcing/selected-references.json';selected=json.loads(p.read_text());report=[]
for code,(value,refs,specs) in choices.items():
 public=json.loads((ROOT/f'sourcing/public/{code}.json').read_text())
 assert public['canPresaleNumber']>0,code
 package='0805' if code in ['C376925','C1779'] else '0402'
 footprint='Phoenix_Passives:C_0805_2012Metric' if package=='0805' else 'Phoenix_Passives:C_0402_1005Metric'
 assert public['componentSpecificationEn']==package,code
 assert all(spec in public['describe'].split() for spec in specs),(code,public['describe'])
 for ref in refs:
  c=components[ref]
  assert c.findtext('value')==value,(ref,c.findtext('value'),value)
  assert c.findtext('footprint')==footprint
  assert not any(ref in v.split() for k,v in selected.items() if k!=code),ref
 selected[code]=' '.join(sorted(set(selected.get(code,'').split()+refs)))
 report.append({'jlc':code,'refs':refs,'catalog_specs':specs,'evidence':f'sourcing/public/{code}.json'})
p.write_text(json.dumps(selected,indent=2)+'\n')
(ROOT/'review/remaining-cap-selection.json').write_text(json.dumps({'status':'CATALOG CANDIDATES ONLY','choices':report,'holds':['X5R effective capacitance at bias and temperature must meet regulator requirements.','Timing capacitor tolerance must be propagated into startup analysis.','Crystal capacitors are initial tuning candidates; stray capacitance, frequency error and oscillator startup remain unqualified.','CQ0402 A tolerance code requires manufacturer guide reconciliation; catalog selection establishes nominal8pF/50V/C0G only.','Catalog quantity is not reserved assembly stock.']},indent=2)+'\n')
print('Assigned',sum(len(v[1]) for v in choices.values()),'positions')
