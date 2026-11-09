#!/usr/bin/env python3
"""Independent topology and slow voltage-window analysis of the upstream protection."""
import itertools,json,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    x=ET.parse(ROOT/'review/integrated.xml');nets={};raw=set()
    for n in x.findall('.//nets/net'):
        for p in n.findall('node'):
            nets[p.get('ref'),p.get('pin')]=n.get('name')
            if n.get('name')=='VBUS_RAW' and not p.get('ref').startswith('#'):raw.add(p.get('ref'))
    assert raw=={'J1','U24','R1901','R1903','C1901','TP2'},raw
    for ref,pin in [('U6','30'),('U11','1'),('U11','3'),('U15','3'),('U15','4'),('R601','1')]:
        assert nets[ref,pin]=='VBUS_PROTECTED',(ref,pin)
    assert nets['U24','4']=='VBUS_PROTECTED' and nets['U24','9']=='VBUS_RAW'
    assert nets['U15','2']=='USB_MAIN_ENABLE' and nets['U15','5']=='+5V_MAIN'
    comps={c.get('ref'):c.findtext('value') for c in x.findall('.//components/comp')}
    for ref,value in [('R1901','35.7k 0.1% 25ppm'),('R1902','10k 0.1% 25ppm'),('R1903','47.5k 0.1% 25ppm'),('R1904','10k 0.1% 25ppm')]:assert comps[ref]==value
    # 0.1% initial tolerance plus25ppm/K *100K for25C ->125C.
    tol=.001+25e-6*100
    def window(top,bottom,thresholds):
        a=[v*(1+rt/rb)+leak*rt for v,rt,rb,leak in itertools.product(thresholds,[top*(1-tol),top*(1+tol)],[bottom*(1-tol),bottom*(1+tol)],[-100e-9,100e-9])]
        return {'min_v':min(a),'max_v':max(a)}
    ov=window(47500,10000,[.97,1.01]);uv=window(35700,10000,[.97,1.01])
    assert ov['min_v']>5.5 and ov['max_v']<6
    report={'status':'PASS TOPOLOGY AND STATIC THRESHOLD SCREEN ONLY','raw_consumers':sorted(raw),
       'resistor_requirement':'0.1% initial, maximum25ppm/K; candidates selected, qualification pending',
       'temperature_screen_c':[-40,125],'drift_span_from_25c_k':100,
       'ovp_rising':ov,'ovp_recovery_falling':window(47500,10000,[.9,.94]),
       'uvlo_rising':uv,'uvlo_falling':window(35700,10000,[.9,.94]),
       'ovp_margin_below_6v_absolute_max_v':6-ov['max_v'],
       'source':'TI SLVSCF3A electrical characteristics',
       'limits':['Static trip window only; response delay/overshoot can exceed this voltage.',
                 '6V is absolute maximum of USB controller/AON LDO, not an operating target.',
                 'Not all downstream component absolute maximum ratings have been closed.',
                 'Rail discharge, fast transient TVS, temperature, load budget and startup require further work.',
                 'UVLO falling threshold is below HD3SS3220 recommended4.5V; brownout sequencing remains unqualified.',
                 'No guaranteed fault selectivity between the two eFuses.']}
    (ROOT/'review/vbus-guard-check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
