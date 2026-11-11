#!/usr/bin/env python3
"""Audit exported candidate netlist, including LPDDR4-specific ZQ polarity."""
import json,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'migration-rk3562/experiments/lpddr4-1gb'
CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
def main():
    xml=P/'review/netlist.xml'
    subprocess.run([CLI,'sch','export','netlist','--format','kicadxml','-o',str(xml),str(P/'kicad/lpddr4-memory-candidate.kicad_sch')],check=True)
    actual={}
    for n in ET.parse(xml).getroot().findall('./nets/net'):
        for node in n.findall('node'):actual[(node.get('ref'),node.get('pin'))]=n.get('name').lstrip('/')
    contract=json.loads((P/'review/lpddr4-memory-candidate-expected.json').read_text())
    for b in contract:
        if b['net'] is not None:assert actual.get((b['ref'],b['pin']))==b['net'],b
    assert actual['U2','A5']==actual['R201','1']=='LPDDR4_ZQ_240R'
    assert actual['R201','2']==actual['U2','B3']=='+1V1_LPDDR4', 'LPDDR4 ZQ resistor must terminate to VDDQ, never GND (datasheet 4.32.2.1)'
    assert actual['U2','F1']=='+1V8_LPDDR4'
    report={'status':'PASS_CONNECTED_PIN_CONTRACT','connected_pins_checked':sum(b['net'] is not None for b in contract),'total_pin_dispositions':len(contract),'ZQ_to_VDDQ_check':'PASS','scope':'Connectivity only; power sources, decoupling, training and physical operation not qualified'}
    (P/'review/netlist-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
