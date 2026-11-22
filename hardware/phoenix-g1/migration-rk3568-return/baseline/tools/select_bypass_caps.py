#!/usr/bin/env python3
"""Assign a stocked candidate to 100nF 0402 positions, preserving qualification holds."""
import json,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    x=ET.parse(ROOT/'review/integrated.xml');refs=[];details=[]
    nets={}
    for n in x.findall('.//nets/net'):
        for pin in n.findall('node'):nets[(pin.get('ref'),pin.get('pin'))]=n.get('name')
    for c in x.findall('.//components/comp'):
        ref=c.get('ref');value=c.findtext('value','')
        if not ref.startswith('C') or value.split()[0]!='100n':continue
        assert c.findtext('footprint')=='Phoenix_Passives:C_0402_1005Metric',ref
        refs.append(ref);details.append({'ref':ref,'value':value,'nets':[nets.get((ref,p)) for p in ['1','2']]})
    assert refs
    source=json.loads((ROOT/'sourcing/public/C1525.json').read_text())
    assert source['componentModelEn']=='CL05B104KO5NNNC'
    assert source['canPresaleNumber']>=len(refs)
    p=ROOT/'sourcing/selected-references.json';groups=json.loads(p.read_text())
    existing={r:code for code,rr in groups.items() for r in rr.split()}
    assert all(existing.get(r,'C1525')=='C1525' for r in refs)
    groups['C1525']=' '.join(sorted(refs));p.write_text(json.dumps(groups,indent=2)+'\n')
    report={'status':'SELECTED CANDIDATE - NOT ELECTRICALLY QUALIFIED','jlc':'C1525',
      'mpn':source['componentModelEn'],'qty':len(refs),'nominal_nf':100,'voltage_rating_v':16,
      'tolerance_percent':10,'dielectric':'X7R','package':'0402','lifecycle':'Mass Production',
      'manufacturer_source':'https://product.samsungsem.com/mlcc/CL05B104KO5NNN.do',
      'source_checked_date':'2026-11-07','positions':details,
      'holds':['DC bias, temperature and aging affect effective capacitance.','USB AC coupling requires channel/impedance review.','Reset/PMIC timing positions require RC tolerance and threshold review.','Placement, loop inductance and full power integrity are not qualified by nominal value.']}
    (ROOT/'review/100nf-selection.json').write_text(json.dumps(report,indent=2)+'\n')
    print(len(refs),'100nF candidates assigned')
if __name__=='__main__':main()
