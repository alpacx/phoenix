#!/usr/bin/env python3
"""Documentary signal mapping only: never mutates the active DDR3 CAD."""
import csv, json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'migration-rk3562'
OUT=BASE/'experiments/lpddr4-1gb'
def main():
    pins={}
    for row in csv.DictReader((BASE/'review/manufacturer-pins.csv').open()):
        for name in row['name'].split('/'):
            if name.startswith('LPDDR4_'):
                assert name not in pins
                pins[name]=row['ball']
    ram={}
    for ch,rows in [('A',('B','C','D','E','F','G','H','J')),('B',('AA','Y','W','V','U','T','R','P'))]:
        b,c,d,e,f,g,h,j=rows
        dq=[b+'2',c+'2',e+'2',f+'2',f+'4',e+'4',c+'4',b+'4',b+'11',c+'11',e+'11',f+'11',f+'9',e+'9',c+'9',b+'9']
        for i,ball in enumerate(dq):ram[f'LPDDR4_DQ{i}_{ch}']=ball
        for i,col in enumerate([3,10]):
            ram[f'LPDDR4_DM{i}_{ch}']=c+str(col)
            ram[f'LPDDR4_DQS{i}P_{ch}']=d+str(col)
            ram[f'LPDDR4_DQS{i}N_{ch}']=e+str(col)
        for i,ball in enumerate([h+'2',j+'2',h+'9',h+'10',h+'11',j+'11']):ram[f'LPDDR4_A{i}_{ch}']=ball
        for name,ball in [('CLKP',j+'8'),('CLKN',j+'9'),('CKE0',j+'4'),('CS0N',h+'4'),('ODT0_CA',g+'2')]:ram[f'LPDDR4_{name}_{ch}']=ball
    ram['LPDDR4_RESETN']='T11'
    assert set(ram)<=set(pins),set(ram)-set(pins)
    assert len(set(ram.values()))==len(ram)
    mapping=[dict(signal=n,soc_ball=pins[n],ram_ball=b) for n,b in sorted(ram.items())]
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'signal-map.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=['signal','soc_ball','ram_ball']);w.writeheader();w.writerows(mapping)
    report={'status':'DOCUMENTARY_DRAFT_NOT_CAD_RELEASE','soc':'RK3562','target_MiB':1024,'candidate':'H9HCNNN8KUMLHR-NME','jlc':'C2912103','signals_mapped':len(mapping),'unmapped_soc_functions':sorted(set(pins)-set(ram)), 'package_mm':[10,15], 'pitch_xy_mm':[0.8,0.65], 'rails_V':{'VDD1':1.8,'VDD2':1.1,'VDDQ':1.1},'shared_ZQ_ball':'A5','source_sha256':hashlib.sha256((OUT/'H9HCNNN8KUMLHR.pdf').read_bytes()).hexdigest(),'holds':['Visual independent ballout review','Full power/ground/NC/DNU map and footprint','PMIC rails and sequencing','Exact chip loader training qualification','PCB escape, length matching, SI and physical tests'], 'active_ddr3_cad_modified':False}
    (OUT/'candidate.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
