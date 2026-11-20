#!/usr/bin/env python3
"""Complete reference inventory with explicit gaps; never an order/assembly BOM."""
import collections,json,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    groups=json.loads((ROOT/'sourcing/selected-references.json').read_text())
    mapping={ref:code for code,refs in groups.items() for ref in refs.split()}
    selected=json.loads((ROOT/'sourcing/selected-main-parts.json').read_text())
    sources={p['jlc']:p for p in selected['parts']}
    assert {c:len(r.split()) for c,r in groups.items()}=={c:p['qty'] for c,p in sources.items()}
    xml=ET.parse(ROOT/'review/integrated.xml')
    rows=[];seen=set()
    for c in xml.findall('.//components/comp'):
        ref=c.get('ref');seen.add(ref)
        row={'ref':ref,'value':c.findtext('value'),'footprint':c.findtext('footprint'),
             'schematic_mpn':c.findtext("fields/field[@name='MPN']"),
             'sheet':c.find('sheetpath').get('names')}
        if ref in mapping:
            source=sources[mapping[ref]]
            row.update({'status':'SELECTED CANDIDATE - NOT QUALIFIED',
                        'jlc':mapping[ref],'selected_mpn':source['mpn'],
                        'unit_usd':source['unit_usd'],'source':source['source']})
        elif ref.startswith('TP'):
            row['status']='PCB TEST LAND - NO PURCHASED COMPONENT'
        else:
            row['status']='MPN NOT SELECTED'
            # These are explicit proposals, not automatic substitutions or release approvals.
            token=row['value'].split()[0]
            if ref.startswith('C') and token in ['100n','22u']:
                code='C1525' if token=='100n' else 'C45783'
                v=json.loads((ROOT/f'sourcing/public/{code}.json').read_text())
                row['proposal']={'jlc':code,'mpn':v['componentModelEn'],'unit_usd':v['initialPrice'],
                                 'hold':'Electrical qualification pending; CL21A226MAQNNNE also NRND. Not included in selected subtotal.'}
        rows.append(row)
    assert set(mapping)<=seen, 'Selected references absent from netlist'
    report={'status':'REVIEW INVENTORY - DO NOT UPLOAD FOR ASSEMBLY',
            'all_netlist_components':len(rows),'counts':dict(collections.Counter(r['status'] for r in rows)),
            'selected_subtotal_usd':selected['subtotal'],
            'selection_quantity_crosscheck':'PASS: reference quantities equal selected sourcing quantities',
            'not_included':'Unselected parts, board, assembly, thermal/mechanical parts, shipping and tax',
            'components':rows}
    (ROOT/'review/bom-inventory.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['counts'])

if __name__=='__main__':main()
