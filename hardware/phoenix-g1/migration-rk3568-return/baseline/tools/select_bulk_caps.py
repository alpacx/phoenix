#!/usr/bin/env python3
"""Select nominally compatible stocked MLCC candidates, not PI qualification."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = [
    ('C52923', 'CL05A105KA5NQNC', '0402', {'1u', '1u / 10V', '1u / 10V X5R'}, 1, 25, 10),
    ('C15850', 'CL21A106KAYNNNE', '0805', {'10u / 10V'}, 10, 25, 10),
    ('C398815', 'CL21A226MOCLRNC', '0805', {'22u / 10V', '22u / 10V X5R', '22u / 6.3V'}, 22, 16, 20),
    ('C23733', 'CL05A475MP5NRNC', '0402', {'4.7u', '4.7u / 10V', '4.7u / 6.3V'}, 4.7, 10, 20),
]

def main():
    path = ROOT / 'sourcing/selected-references.json'
    groups = json.loads(path.read_text())
    existing = {r:code for code, refs in groups.items() for r in refs.split()}
    components = ET.parse(ROOT/'review/integrated.xml').findall('.//components/comp')
    report = []
    for code, mpn, package, values, uf, volts, tolerance in RULES:
        source = json.loads((ROOT/f'sourcing/public/{code}.json').read_text())
        assert source['componentModelEn'] == mpn
        assert source['componentSpecificationEn'] == package
        assert all(s in source['describe'] for s in (str(volts)+'V', 'X5R', '±'+str(tolerance)+'%'))
        refs = []
        for c in components:
            ref = c.get('ref')
            if not ref.startswith('C') or c.findtext('value') not in values:
                continue
            expected_fp = 'Phoenix_Passives:C_' + {'0402':'0402_1005Metric','0805':'0805_2012Metric'}[package]
            if c.findtext('footprint') != expected_fp:
                continue
            assert existing.get(ref, code) == code
            refs.append(ref)
        assert source['canPresaleNumber'] >= len(refs)
        groups[code] = ' '.join(sorted(refs))
        report.append({'jlc':code, 'mpn':mpn, 'refs':refs, 'nominal_uf':uf,
                       'rated_v':volts, 'tolerance_percent':tolerance, 'temperature_range_c':[-55,85],
                       'manufacturer_source':'https://product.samsungsem.com/mlcc/'+mpn[:-1]+'.do',
                       'manufacturer_status_observed':'Mass Production',
                       'checked_date':'2026-11-08'})
    path.write_text(json.dumps(groups, indent=2)+'\n')
    (ROOT/'review/bulk-cap-selection.json').write_text(json.dumps({
        'status':'NOMINAL CANDIDATES SELECTED; EFFECTIVE CAPACITANCE NOT QUALIFIED',
        'parts':report,
        'limits':['Explicit X7R positions excluded; X5R is not a substitute for them.',
                  'Voltage rating does not establish capacitance at operating DC bias.',
                  '85C body-temperature limit must be checked in passive enclosure.',
                  'Tolerance, DC bias, aging, ESR and converter stability remain unqualified.',
                  'No assumption that 25V parts guarantee more effective capacitance than another 10V part.']
    }, indent=2)+'\n')
    print(sum(len(p['refs']) for p in report), 'MLCC candidate positions selected')

if __name__ == '__main__':
    main()
