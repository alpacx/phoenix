#!/usr/bin/env python3
"""Build a connected hierarchy from draft sheets, preserving standalone source studies.
Global labels are deliberate system nets; no ERC suppression or inferred power flags.
"""
from schematic_builder import *
import shutil

def main():
 dest=ROOT/'kicad/integrated';dest.mkdir(exist_ok=True)
 rootid=str(uuid.uuid5(uuid.NAMESPACE_URL,'phoenix-g1/integrated/root'))
 items=[];contracts=[];seen={};pages=[]
 groups=json.loads((ROOT/'sourcing/selected-references.json').read_text())
 sources={p['jlc']:p for p in json.loads((ROOT/'sourcing/selected-main-parts.json').read_text())['parts']}
 selected={ref:sources[code] for code,refs in groups.items() for ref in refs.split()}
 overrides=json.loads((ROOT/'review/footprint-overrides.json').read_text()) if (ROOT/'review/footprint-overrides.json').exists() else {}
 names=[p.name.removesuffix('-expected.json') for p in sorted((ROOT/'review').glob('*-expected.json'))]
 for idx,name in enumerate(names):
  sch=sx.loads((ROOT/f'kicad/{name}.kicad_sch').read_text());sheetid=str(uuid.uuid5(uuid.NAMESPACE_URL,'phoenix-g1/integrated/'+name))
  for label in fields(sch,'label'):
   label[0]=sx.Symbol('global_label');label.insert(2,[sx.Symbol('shape'),sx.Symbol('bidirectional')])
   # Long supply names on vertical labels crossed page borders and adjacent rows.
   # Rotate the text at the unchanged electrical anchor; wires and pins do not move.
   at=fields(label,'at')[0]
   if at[3] in [90,270]:
    at[3]=0
    effects=fields(label,'effects')[0]
    for justify in fields(effects,'justify'):justify[:]=[sx.Symbol('justify'),sx.Symbol('right'),sx.Symbol('bottom')]
  for symbol in fields(sch,'symbol'):
   for prop in fields(symbol,'property'):
    if prop[1]=='Footprint' and prop[2] in overrides:prop[2]=overrides[prop[2]]
   ref=next(p[2] for p in fields(symbol,'property') if p[1]=='Reference');unit=fields(symbol,'unit')[0][1]
   if ref in selected:
    for field,value in [('MPN',selected[ref]['mpn']),('JLCPCB',selected[ref]['jlc']),('Qualification','CANDIDATE - NOT QUALIFIED')]:
     props=[v for v in fields(symbol,'property') if v[1]==field]
     if props:props[0][2]=value
     else:symbol.append(sx.loads(f'(property {q(field)} {q(value)} (at 0 0 0) (effects (font (size 1 1)) (hide yes)))'))
   key=(ref,unit)
   if key in seen:raise ValueError(f'Duplicate instance {key}: {seen[key]} / {name}')
   seen[key]=name
   for old in fields(symbol,'instances'):symbol.remove(old)
   symbol.append(sx.loads(f'(instances (project "phoenix-g1" (path "/{rootid}/{sheetid}" (reference {q(ref)}) (unit {unit}))))'))
  (dest/f'{name}.kicad_sch').write_text(sx.dumps(sch)+'\n')
  cols=6 if len(names)>30 else 5
  step=65 if cols==6 else 79
  width=57 if cols==6 else 70
  x=15+(idx%cols)*step;y=25+(idx//cols)*36
  items.append(f'(sheet (at {x} {y}) (size {width} 25) (stroke (width 0) (type default)) (fill (color 0 0 0 0)) (uuid "{sheetid}") (property "Sheetname" {q(name)} (at {x} {y-1} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) (property "Sheetfile" {q(name+".kicad_sch")} (at {x} {y+26} 0) (effects (font (size 1 1)) (justify left top))) (instances (project "phoenix-g1" (path "/{rootid}" (page "{idx+2}")))))')
  rows=json.loads((ROOT/f'review/{name}-expected.json').read_text())
  for r in rows:r['sheet']=name
  contracts.extend(rows);pages.append(name)
 text=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid "{rootid}") (paper "A3") (title_block (title "Phoenix G1 - integrated engineering draft") (rev "DRAFT") (comment 1 "Not for fabrication")) (lib_symbols)'+''.join(items)+f'(sheet_instances (path "/" (page "1"))))\n'
 (dest/'phoenix-g1.kicad_sch').write_text(text)
 (dest/'phoenix-g1.kicad_pro').write_text(json.dumps({'meta':{'filename':'phoenix-g1.kicad_pro','version':1}},indent=2)+'\n')
 for table in ['sym-lib-table','fp-lib-table']:
  (dest/table).write_text((ROOT/'kicad'/table).read_text().replace('${KIPRJMOD}/','${KIPRJMOD}/../'))
 (ROOT/'review/integrated-contract.json').write_text(json.dumps(contracts,indent=2)+'\n')
 (ROOT/'review/integrated-manifest.json').write_text(json.dumps({'status':'INCOMPLETE ENGINEERING DRAFT','sheets':pages,'pin_dispositions':len(contracts),'instances':len(seen),'excluded':'legacy display-interface study superseded by display-power and display-signals; display footprint still pending'},indent=2)+'\n')
 print(len(pages),'sheets;',len(contracts),'pin dispositions;',len(seen),'symbol units')
if __name__=='__main__':main()
