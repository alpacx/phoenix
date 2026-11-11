#!/usr/bin/env python3
"""Isolated memory candidate sheet with explicit unqualified power inputs."""
import csv,json
from pathlib import Path
import sexpdata as sx
import schematic_builder as sb
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'migration-rk3562/experiments/lpddr4-1gb'
def main():
    balls=list(csv.DictReader((OUT/'ball-disposition.csv').open()))
    for b in balls:b['net']=b['net'] or None
    groups=[[],[],[],[]]
    for b in balls:
        n=b['name'];g=0 if n.endswith('_A') else 1 if n.endswith('_B') else 2 if n in ('VDD1','VDD2','VDDQ') else 3
        groups[g].append(b)
    name='H9HCNNN8KUMLHR_NME_DRAFT'
    symbol=[f'(symbol "{name}" (pin_names (offset 0.5)) (in_bom yes) (on_board yes)', '(property "Reference" "U" (at 0 0 0) (effects (font (size 1 1))))', f'(property "Value" "{name}" (at 0 0 0) (effects (font (size 1 1))))']
    for unit,group in enumerate(groups,1):
        symbol.append(f'(symbol "{name}_{unit}_1"')
        for i,b in enumerate(group):
            # Two pin columns; 41 rows maximum.
            side=i%2; y=round(50.8-(i//2)*2.54,4);x=-15.24 if side==0 else 15.24;a=0 if side==0 else 180
            n=b['name'];kind='power_in' if n in ('VDD1','VDD2','VDDQ','VSS') else 'no_connect' if n in ('NC','DNU') else 'passive' if n=='ZQ0' else 'bidirectional' if n.startswith(('DQ','DMI')) else 'input'
            symbol.append(f'(pin {kind} line (at {x} {y} {a}) (length 2.54) (name "{n}" (effects (font (size 0.7 0.7)))) (number "{b["ball"]}" (effects (font (size 0.7 0.7)))))')
        symbol.append(')')
    symbol.append(')');sym=sx.loads(''.join(symbol))
    symbols=sb.load_symbols([],['R']);symbols[name]=sym
    sb.ROOT=OUT
    (OUT/'kicad').mkdir(exist_ok=True);(OUT/'review').mkdir(exist_ok=True)
    sheet=sb.Sheet('lpddr4-memory-candidate','Phoenix RK3562 - LPDDR4 1 GB candidate','Phoenix_LPDDR4',symbols)
    for unit,group in enumerate(groups,1):
        sheet.place(name,'U2',63.5+95.25*(unit-1),76.2,{b['ball']:b['net'] for b in group},mpn='H9HCNNN8KUMLHR-NME',unit=unit,fp='Phoenix_LPDDR4_Draft:H9HCNNN8KUMLHR_FBGA200_10x15_P0.8x0.65_DRAFT')
    sheet.place('R','R201',63.5,190.5,{'1':'LPDDR4_ZQ_240R','2':'+1V1_LPDDR4'},value='240R 1% candidate',fp='Phoenix_Passives:R_0402_1005Metric')
    for i,t in enumerate(['DRAFT: not integrated into main schematic. Power sources and decoupling are incomplete.', 'VDD1 1.8 V must ramp no later than VDD2 1.1 V; VDDQ also 1.1 V.', 'No DDR3 VREF divider retained. Firmware training and exact-part qualification pending.', '200-ball map checked against Hynix Rev1.1 p6; footprint pads remain provisional.', 'U2 units: channel A, channel B, supplies, ground/control/unused. U3 removed only in future integrated revision.']):sheet.note(t,20,220+i*6)
    sheet.save()
    (OUT/'kicad/Phoenix_LPDDR4.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor")'+''.join(sx.dumps(s) for s in symbols.values())+')\n')
if __name__=='__main__':main()
