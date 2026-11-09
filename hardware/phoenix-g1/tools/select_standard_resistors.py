#!/usr/bin/env python3
"""Assign observed stocked1%0402 candidates only to matching <=1% requests.
Selection is not electrical/thermal qualification. Does not replace precision parts.
"""
import json,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
mapping={'10k':'C25744','100k':'C25741','47k':'C25792','4.7k':'C25900','22R':'C25092','1M':'C26083','1k':'C11702','100R':'C25076','200k':'C25764','120R':'C25079','51k':'C25794','2.2k':'C25879','2.49k':'C145071','180k':'C2906402','240R':'C114755','1.8k':'C163481'}
p=ROOT/'sourcing/selected-references.json';selected=json.loads(p.read_text());used={ref:code for code,refs in selected.items() for ref in refs.split()};assigned=[]
for c in ET.parse(ROOT/'review/integrated.xml').findall('.//components/comp'):
 ref=c.get('ref');value=c.findtext('value','');fp=c.findtext('footprint','');tokens=value.split()
 if not ref.startswith('R') or not tokens or tokens[0] not in mapping or fp!='Phoenix_Passives:R_0402_1005Metric':continue
 if len(tokens)>1 and tokens[1:]!=['1%']:continue
 code=mapping[tokens[0]]
 public=json.loads((ROOT/f'sourcing/public/{code}.json').read_text())
 expected=tokens[0].replace('R','')+'Ω'
 assert expected in public['describe'].split(),(ref,code,expected)
 if ref in used:
  assert used[ref]==code,(ref,used[ref],code)
  continue
 public=json.loads((ROOT/f'sourcing/public/{code}.json').read_text())
 assert public['canPresaleNumber']>0 and public['componentSpecificationEn']=='0402'
 assert '±1%' in public['describe'] and '62.5mW' in public['describe']
 selected[code]=' '.join(selected.get(code,'').split()+[ref]);assigned.append({'ref':ref,'value':value,'jlc':code})
p.write_text(json.dumps(selected,indent=2)+'\n')
(ROOT/'review/standard-resistors-selection.json').write_text(json.dumps({'status':'CANDIDATES SELECTED - NOT QUALIFIED','sources':['sourcing/public/'+c+'.json' for c in mapping.values()],'assigned_this_run':assigned,'all_selected_standard_refs':{code:selected.get(code,'').split() for code in mapping.values()},'limits':['50V and62.5mW catalog rating are not operating-temperature derated limits.','100ppm/C candidates do not satisfy0.1%/25ppm requests; precision positions are excluded.','Divider drift, pulse load, high-frequency behavior and resistor operating power still require review.','No zero-ohm power links or RF matching components selected by this script.']},indent=2)+'\n')
print(len(assigned),'new resistor candidates assigned')
