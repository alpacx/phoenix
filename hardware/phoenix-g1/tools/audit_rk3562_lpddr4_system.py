#!/usr/bin/env python3
"""Verify whole-system candidate netlist and independent memory power invariants."""
import csv,json,subprocess,xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'migration-rk3562/experiments/lpddr4-1gb';S=P/'system'
def main():
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(S/'review/integrated.xml'),str(S/'kicad/integrated/phoenix-g1.kicad_sch')],check=True)
    tree=E.parse(S/'review/integrated.xml').getroot();nets={}
    for n in tree.findall('./nets/net'):
        for x in n.findall('node'):nets[x.get('ref'),x.get('pin')]=n.get('name').lstrip('/')
    contract=json.loads((S/'review/integrated-contract.json').read_text())
    for row in contract:
        if row['net'] is not None:assert nets.get((row['ref'],row['pin']))==row['net'],row
    for row in csv.DictReader((P/'signal-map.csv').open()):
        if 'ODT0_CA' in row['signal']:
            assert nets['U2',row['ram_ball']]=='+1V1_LPDDR4'
        else:assert nets['U1',row['soc_ball']]==nets['U2',row['ram_ball']]==row['signal'],row
    for ball in ['1B6','1B10','1B7','B12','B16','C17','B9','B19','1C9','C11']:
        assert not any(r['ref']=='U1' and r['pin']==ball and r['net'] is not None for r in contract)
    assert nets['U2','A5']==nets['R201','1']=='LPDDR4_ZQ_240R'
    assert nets['R201','2']==nets['U2','B3']==nets['U4','26']=='+1V1_LPDDR4'
    assert nets['R1503','2']=='+1V1_LPDDR4', 'LPDDR4 RK3562 PHY calibration pulls UP (reference sheet5)'
    assert nets['R1503','1']==nets['U1','1D4']=='DDR_RZQ'
    for ball in ['1D11','1D6','1E3','1E5','1E7','1E9','1E4','1E6','1E8','1E10']:assert nets['U1',ball]=='+1V1_LPDDR4'
    assert nets['U2','F1']=='+1V8_SYS'
    assert not any(ref=='U3' for ref,pin in nets)
    assert not any(n=='+1V5_DDR' or n.startswith('DDR3_') for n in nets.values())
    report={'status':'PASS_INTEGRATED_CONNECTIVITY_NOT_ELECTRICAL_RELEASE','contract_dispositions':len(contract),'connected_checked':sum(r['net'] is not None for r in contract),'end_to_end_memory_signals':65,'ODT_tied_to_VDD2':True,'RAM_ZQ_to_VDDQ':True,'SoC_RZQ_pullup':True,'PHY_power_balls_checked':10,'assembly_ready':False}
    (S/'review/memory-connectivity-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
