#!/usr/bin/env python3
"""DDR3 signal allocation from vendor pinouts, prior to schematic/layout release."""
import csv
import json
from pathlib import Path
import sexpdata as sx
from audit_rk3568 import fields, walk

ROOT=Path(__file__).resolve().parents[1]
# Hynix Rev 1.2 page 6, visually checked including overbars.
ROWS={
'A':'VDDQ DQU5 DQU7 DQU4 VDDQ VSS',
'B':'VSSQ VDD VSS ~{DQSU} DQU6 VSSQ',
'C':'VDDQ DQU3 DQU1 DQSU DQU2 VDDQ',
'D':'VSSQ VDDQ DMU DQU0 VSSQ VDD',
'E':'VSS VSSQ DQL0 DML VSSQ VDDQ',
'F':'VDDQ DQL2 DQSL DQL1 DQL3 VSSQ',
'G':'VSSQ DQL6 ~{DQSL} VDD VSS VSSQ',
'H':'VREFDQ VDDQ DQL4 DQL7 DQL5 VDDQ',
'J':'NC VSS ~{RAS} CK VSS NC',
'K':'ODT VDD ~{CAS} ~{CK} VDD CKE',
'L':'NC ~{CS} ~{WE} A10/AP ZQ NC',
'M':'VSS BA0 BA2 NC VREFCA VSS',
'N':'VDD A3 A0 A12/~{BC} BA1 VDD',
'P':'VSS A5 A2 A1 A4 VSS',
'R':'VDD A7 A9 A11 A6 VDD',
'T':'VSS ~{RESET} A13 NC A8 VSS'}

def main():
    official={r+str(c):n for r,row in ROWS.items() for c,n in zip([1,2,3,7,8,9],row.split())}
    lib=sx.loads((ROOT/'kicad/Phoenix_Candidates.kicad_sym').read_text())
    symbol=next(s for s in fields(lib,'symbol') if s[1]=='H5TQ2G63GFR-TEC')
    imported={str(fields(p,'number')[0][1]):fields(p,'name')[0][1] for p in walk(symbol,'pin')}
    assert official==imported, 'Imported RAM symbol disagrees with manufacturer ballout'
    soc=list(csv.DictReader((ROOT/'review/rk3568-manufacturer-pins.csv').open()))
    lookup={f:r['ball'] for r in soc for f in r['functions'].split(' | ') if f.startswith('DDR3_')}
    signals=[]
    for ref,offset in [('U2',0),('U3',16)]:
        for ball,name in official.items():
            socball=None
            if name=='NC': net=None
            elif name in ('VDD','VDDQ'):net='+1V5_DDR'
            elif name in ('VSS','VSSQ'):net='GND'
            elif name=='VREFDQ':net='DDR_VREFDQ';socball='P8'
            elif name=='VREFCA':net='DDR_VREFCA'
            elif name=='ZQ':net=ref+'_ZQ_240R_TO_GND'
            else:
                if name.startswith('DQL'): function='DDR3_DQ'+str(offset+int(name[3:]))
                elif name.startswith('DQU'):function='DDR3_DQ'+str(offset+8+int(name[3:]))
                elif name in ('DML','DMU'):function='DDR3_DM'+str(offset//8+(name=='DMU'))
                elif name in ('DQSL','~{DQSL}','DQSU','~{DQSU}'):
                    function='DDR3_DQS'+str(offset//8+('U' in name))+('N' if name.startswith('~') else 'P')
                else:
                    function={'CK':'DDR3_CLKP','~{CK}':'DDR3_CLKN','CKE':'DDR3_CKE','ODT':'DDR3_ODT0',
                        '~{CS}':'DDR3_CS0N','~{RAS}':'DDR3_RASN','~{CAS}':'DDR3_CASN','~{WE}':'DDR3_WEN',
                        '~{RESET}':'DDR3_RESETN','A10/AP':'DDR3_A10','A12/~{BC}':'DDR3_A12'}.get(name,'DDR3_'+name)
                socball=lookup[function];net=function
            signals.append({'ram_ref':ref,'ram_ball':ball,'ram_pin':name,'logical_net':net,'soc_ball':socball})
    assert len(signals)==192
    result={'status':'SIGNAL ALLOCATION ONLY - clock termination, power and decoupling NOT implemented',
        'configuration':{'ram_mpn':'H5TQ2G63GFR-TEC','ram_count':2,'capacity_bytes':536870912,
            'bus_width_bits':32,'ranks':1,'ecc':False,'vdd_vddq_v':1.5,
            'initial_target_clock_mhz':533,'initial_target_data_rate_mt_s':1066,
            'frequency_status':'Design target only; loader configuration and memory training untested'},
        'sources':['Hynix Rev 1.2 Oct 2015 pp 3-6','Rockchip RK3568 PinOut V1.1','Rockchip Hardware Design Guide V1.2 pp 12-17'],
        'mandatory_circuits':['RK3568 H7 DDR_RZQ: 120 ohm 1% to GND',
            'Each RAM L8 ZQ: separate 240 ohm 1% to GND',
            'VREFCA: two 1k 1% divider from +1V5_DDR; vendor-specified 1nF filtering',
            'VREFDQ: SoC P8, 1nF filtering per vendor reference',
            'PMIC BUCK3 feedback configured for 1.5V before first DDR initialization',
            'DDR power sequence, all decoupling and clock matching must be implemented before routing'],
        'unresolved':['Two-device DDR3 topology must be qualified; available Rockchip DDR3 template is four-device/two-rank.',
            'Do not copy DDR4 address mapping: RK3568 AC pins have different DDR3 functions.',
            'No byte swapping is applied in this allocation. Any PCB swap must update loader configuration.',
            'No 1.35V substitution: selected H5TQ part specifies 1.425-1.575V.'],
        'signals':signals}
    (ROOT/'review/ddr3-signal-plan.json').write_text(json.dumps(result,indent=2)+'\n')
    print('96 RAM ball names matched; allocated 192 RAM pin dispositions for 512 MiB, x32, one rank.')

if __name__=='__main__':main()
