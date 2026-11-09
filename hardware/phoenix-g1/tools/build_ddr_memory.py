#!/usr/bin/env python3
"""Generate the two-device DDR3 draft from the audited ball allocation."""
import copy
import json
import math
import shutil
import uuid
from pathlib import Path
import sexpdata as sx
from audit_rk3568 import fields, walk

ROOT=Path(__file__).resolve().parents[1]
NAME='ddr3-memory'
def uid(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'phoenix-g1/'+NAME+'/'+s))
def q(s):return json.dumps(str(s))

def main():
    candidates=sx.loads((ROOT/'kicad/Phoenix_Candidates.kicad_sym').read_text())
    device=sx.loads(Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/Device.kicad_sym').read_text())
    names=['H5TQ2G63GFR-TEC']
    symbols={n[1]:copy.deepcopy(n) for n in fields(candidates,'symbol') if n[1] in names}
    symbols.update({n[1]:copy.deepcopy(n) for n in fields(device,'symbol') if n[1] in ('R','C')})
    for name,symbol in symbols.items():
        for prop in fields(symbol,'property'):
            prop[:]=[e for e in prop if not(isinstance(e,list) and e and str(e[0])=='id')]
        for pin in walk(symbol,'pin'):
            pname=fields(pin,'name')[0][1]
            if name=='H5TQ2G63GFR-TEC':
                kind='input'
                if pname in ('VDD','VDDQ','VSS','VSSQ'):kind='power_in'
                elif pname=='NC':kind='no_connect'
                elif 'DQ' in pname and pname!='VREFDQ':kind='bidirectional'
                elif pname=='ZQ':kind='passive'
                pin[1]=sx.Symbol(kind)
    (ROOT/'kicad/Phoenix_Memory.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor")'+''.join(sx.dumps(s) for s in symbols.values())+')\n')
    fpdir=ROOT/'kicad/Phoenix_Passives.pretty';fpdir.mkdir(exist_ok=True)
    for library,name in [('Capacitor_SMD','C_0805_2012Metric'),('Capacitor_SMD','C_0402_1005Metric'),('Resistor_SMD','R_0402_1005Metric')]:
        shutil.copyfile(Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')/(library+'.pretty')/(name+'.kicad_mod'),fpdir/(name+'.kicad_mod'))
    root=uid('root'); content=[]; contract=[]; used=set()
    def place(name,ref,x,y,nets,value=None,footprint=None):
        symbol=symbols[name];used.add(name)
        pins=list(walk(symbol,'pin'))
        assert {str(fields(p,'number')[0][1]) for p in pins}==set(nets),ref
        props={p[1]:p[2] for p in fields(symbol,'property')}
        fp=footprint or props.get('Footprint','')
        top=max(fields(p,'at')[0][2] for p in pins)
        body=f'(symbol (lib_id {q("Phoenix_Memory:"+name)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {q(uid(ref))})'
        xx=x+12 if name in ('R','C') else x
        for k,v,yy,hide in [('Reference',ref,y-top-9,False),('Value',value or name,y-top-6.5,False),('Footprint',fp,y,True),('Qualification','DRAFT; passive MPNs, topology and layout not qualified',y,True)]:
            body+=f'(property {q(k)} {q(v)} (at {xx} {yy} 0) (effects (font (size 1 1))'+(' hide' if hide else '')+'))'
        body+=f'(instances (project {q(NAME)} (path {q("/"+root)} (reference {q(ref)}) (unit 1)))))'
        content.append(body)
        for pin in pins:
            num=str(fields(pin,'number')[0][1]);net=nets[num]
            px,py,angle=fields(pin,'at')[0][1:];px=round(x+px,4);py=round(y-py,4)
            if net is None:
                content.append(f'(no_connect (at {px} {py}) (uuid {q(uid(ref+num+"nc"))}))')
                contract.append({'ref':ref,'pin':num,'pin_name':fields(pin,'name')[0][1],'net':None})
                continue
            ex=round(px-5.08*math.cos(math.radians(angle)),4);ey=round(py+5.08*math.sin(math.radians(angle)),4)
            content.append(f'(wire (pts (xy {px} {py}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid {q(uid(ref+num+"wire"))}))')
            a=90 if angle in (90,270) else 0;j='right' if angle in (0,90) else 'left'
            content.append(f'(label {q(net)} (at {ex} {ey} {a}) (effects (font (size 1 1)) (justify {j} bottom)) (uuid {q(uid(ref+num+"label"))}))')
            contract.append({'ref':ref,'pin':num,'pin_name':fields(pin,'name')[0][1],'net':net})
    plan=json.loads((ROOT/'review/ddr3-signal-plan.json').read_text())
    for ref,x in [('U2',95.25),('U3',231.14)]:
        nets={s['ram_ball']:s['logical_net'] for s in plan['signals'] if s['ram_ref']==ref}
        place('H5TQ2G63GFR-TEC',ref,x,99.06,nets)
    for ref,x,net in [('R201',35.56,'U2_ZQ_240R_TO_GND'),('R301',99.06,'U3_ZQ_240R_TO_GND')]:
        place('R',ref,x,187.96,{'1':net,'2':'GND'},'240R 1%','Phoenix_Passives:R_0402_1005Metric')
    place('R','R401',162.56,187.96,{'1':'+1V5_DDR','2':'DDR_VREFCA'},'1k 1%','Phoenix_Passives:R_0402_1005Metric')
    place('R','R402',226.06,187.96,{'1':'DDR_VREFCA','2':'GND'},'1k 1%','Phoenix_Passives:R_0402_1005Metric')
    for ref,x,net in [('C401',289.56,'DDR_VREFCA'),('C402',353.06,'DDR_VREFDQ')]:
        place('C',ref,x,187.96,{'1':net,'2':'GND'},'1n / C0G','Phoenix_Passives:C_0402_1005Metric')
    notes=[
        'DDR3 DRAFT: 2 x H5TQ2G63GFR-TEC, 512 MiB, 32-bit bus, one rank. NO FABRICATION RELEASE.',
        'All 192 RAM ball dispositions checked against manufacturer ballout and RK3568 DDR3 alternate functions.',
        'DDR_VREFDQ is driven by RK3568 ball P8; do not connect it to the VREFCA divider.',
        'Both VDD and VDDQ require 1.50 V. This H5TQ part is not a 1.35 V DDR3L device.',
        'RZQ 120R 1% from RK3568 H7 to GND belongs on the SoC sheet; not implemented here.',
        'Power decoupling, clock termination and topology review remain mandatory before routing.',
        'VREF filtering placement and distributed decoupling must follow final physical topology.',
        'Initial target 533 MHz CK / 1066 MT/s; no training or throughput measurement performed.',
        'Passive values are design requirements; exact MPNs and availability have not been qualified.',
        'Sources: Hynix Rev1.2 p6; RK3568 PinOut V1.1; Rockchip Hardware Design Guide V1.2.'
    ]
    for i,t in enumerate(notes):content.append(f'(text {q(t)} (at 15 {211+i*5.08} 0) (effects (font (size 1 1)) (justify left)) (uuid {q(uid("note"+str(i)))}))')
    embedded=[]
    for name in sorted(used):
        s=copy.deepcopy(symbols[name]);s[1]='Phoenix_Memory:'+name;embedded.append(sx.dumps(s))
    sch=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {q(root)}) (paper "A3") (title_block (title "Phoenix G1 - 512 MiB DDR3 memory") (rev "DRAFT") (comment 1 "Not for fabrication")) (lib_symbols '+''.join(embedded)+')'+''.join(content)+')\n'
    (ROOT/f'kicad/{NAME}.kicad_sch').write_text(sch)
    (ROOT/f'kicad/{NAME}.kicad_pro').write_text(json.dumps({'meta':{'filename':NAME+'.kicad_pro','version':1}},indent=2)+'\n')
    (ROOT/'review/ddr3-memory-expected.json').write_text(json.dumps(contract,indent=2)+'\n')
    print(f'DDR3 draft: {len(contract)} pin dispositions, including 192 RAM balls.')

if __name__=='__main__':main()
