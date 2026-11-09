#!/usr/bin/env python3
"""Generate the RK860-0 CPU supply draft, with explicit off-sheet interfaces."""
import copy
import json
import math
import shutil
import uuid
from pathlib import Path
import sexpdata as sx
from audit_rk3568 import fields, walk

ROOT=Path(__file__).resolve().parents[1]
NAME='cpu-power'
def uid(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'phoenix-g1/'+NAME+'/'+s))
def q(s):return json.dumps(str(s))

def main(target="RK3568"):
    sense_net="VDD_CPU_COM" if target=="RK3568" else "CPU_FB_SENSE"
    candidates=sx.loads((ROOT/'kicad/Phoenix_Candidates.kicad_sym').read_text())
    device=sx.loads(Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/Device.kicad_sym').read_text())
    names=['RK860-0','FNR5020SR24NT']
    symbols={n[1]:copy.deepcopy(n) for n in fields(candidates,'symbol') if n[1] in names}
    symbols.update({n[1]:copy.deepcopy(n) for n in fields(device,'symbol') if n[1] in ('R','C')})
    expected_cpu={'A1':'VSEL','A2':'EN','A3':'SCL','A4':'VOUT','B1':'SDA','B2':'GND','B3':'GND','B4':'AGND','C1':'GND','C2':'GND','C3':'GND','C4':'GND','D1':'VIN','D2':'VIN','D3':'LX','D4':'LX','E1':'VIN','E2':'VIN','E3':'LX','E4':'LX'}
    actual_cpu={str(fields(p,'number')[0][1]):fields(p,'name')[0][1] for p in walk(symbols['RK860-0'],'pin')}
    assert expected_cpu==actual_cpu, 'CPU regulator symbol does not match RK860 Rev1.2 p4'
    for name,symbol in symbols.items():
        for prop in fields(symbol,'property'):
            prop[:]=[e for e in prop if not(isinstance(e,list) and e and str(e[0])=='id')]
        for pin in walk(symbol,'pin'):
            pname=fields(pin,'name')[0][1]
            if name=='RK860-0':
                # VOUT is a sense input despite the datasheet's I/O-column typo.
                kind={'VIN':'power_in','GND':'power_in','AGND':'power_in','LX':'power_out','SDA':'bidirectional'}.get(pname,'input')
                # Four LX balls are one internal switch node, not four supplies.
                if pname=='LX' and str(fields(pin,'number')[0][1])!='D3':kind='passive'
                pin[1]=sx.Symbol(kind)
            elif name=='FNR5020SR24NT':pin[1]=sx.Symbol('passive')
    (ROOT/'kicad/Phoenix_Power.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor")'+''.join(sx.dumps(s) for s in symbols.values())+')\n')
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
        body=f'(symbol (lib_id {q("Phoenix_Power:"+name)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {q(uid(ref))})'
        xx=x+12 if name in ('R','C') else x
        for k,v,yy,hide in [('Reference',ref,y-top-9,False),('Value',value or name,y-top-6.5,False),('Footprint',fp,y,True),('Qualification','DRAFT; passive MPNs and transient response not qualified',y,True)]:
            body+=f'(property {q(k)} {q(v)} (at {xx} {yy} 0) (effects (font (size 1 1))'+(' hide' if hide else '')+'))'
        body+=f'(instances (project {q(NAME)} (path {q("/"+root)} (reference {q(ref)}) (unit 1)))))'
        content.append(body)
        for pin in pins:
            num=str(fields(pin,'number')[0][1]);net=nets[num]
            px,py,angle=fields(pin,'at')[0][1:];px=round(x+px,4);py=round(y-py,4)
            ex=round(px-5.08*math.cos(math.radians(angle)),4);ey=round(py+5.08*math.sin(math.radians(angle)),4)
            content.append(f'(wire (pts (xy {px} {py}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid {q(uid(ref+num+"wire"))}))')
            a=90 if angle in (90,270) else 0;j='right' if angle in (0,90) else 'left'
            content.append(f'(label {q(net)} (at {ex} {ey} {a}) (effects (font (size 1 1)) (justify {j} bottom)) (uuid {q(uid(ref+num+"label"))}))')
            contract.append({'ref':ref,'pin':num,'pin_name':fields(pin,'name')[0][1],'net':net})
    cpu={b: {'VSEL':'PMIC_SLEEP','EN':'CPU_BUCK_EN','SCL':'I2C0_SCL','SDA':'I2C0_SDA','VOUT':sense_net,'VIN':'+5V_MAIN','LX':'CPU_SW','GND':'GND','AGND':'GND'}[n] for b,n in expected_cpu.items()}
    place('RK860-0','U10',127,57.15,cpu)
    place('FNR5020SR24NT','L1001',215.9,57.15,{'1':'CPU_SW','2':'VDD_CPU'},'240nH - candidate')
    for i in range(2):place('C',f'C{1001+i}',38.1+i*38.1,57.15,{'1':'+5V_MAIN','2':'GND'},'22u / 10V X5R','Phoenix_Passives:C_0805_2012Metric')
    for i in range(4):place('C',f'C{1011+i}',38.1+i*50.8,119.38,{'1':'VDD_CPU','2':'GND'},'22u / 10V X5R','Phoenix_Passives:C_0805_2012Metric')
    place('R','R1001',38.1,177.8,{'1':'VDD_CPU','2':sense_net},'100R 1%','Phoenix_Passives:R_0402_1005Metric')
    # Reference schematic page 23: feed-forward capacitor across output and
    # remote-sense node, NOT from feedback to ground.
    place('C','C1020',88.9,177.8,{'1':'VDD_CPU','2':sense_net},'1u / 10V X5R','Phoenix_Passives:C_0402_1005Metric')
    place('R','R1002',139.7,177.8,{'1':'+3V3_PMU','2':'CPU_BUCK_EN'},'51k 1%','Phoenix_Passives:R_0402_1005Metric')
    notes=[
        'CPU POWER - DRAFT. Not a complete or release-qualified power system.',
        'RK860-0: I2C address 0x40, DIE_ID=0x8, default 1.000 V, 12.5 mV step. No substitution with -2/-3.',
        ('VDD_CPU_COM is the RK3568 M15 remote-sense ball. Route separately from the high-current output path.' if target=='RK3568' else 'CPU_FB_SENSE is the regulator feedback net, NOT an RK3562 ball. RK860 p4 specifies sensing at the output capacitor.'),
        f'R1001 and C1020 bridge VDD_CPU to {sense_net}; C1020 is NOT a feedback-to-ground capacitor.',
        'Input +5V_MAIN must be current-qualified and inrush-limited. +3V3_PMU enables CPU at the PMIC stage.',
        'Add 4 x 22uF at the SoC CPU balls: total nominal CPU output capacitance becomes 176uF.',
        'Effective capacitance must exceed the vendor requirement after tolerance, bias and temperature; MPNs pending.',
        'Inductor candidate must pass Isat/Irms, ripple and thermal review; catalog current alone is insufficient.',
        'I2C pull-ups and PMIC_SLEEP bias belong to the PMIC/SoC circuit; do not add duplicate pull-ups here.',
        ('Sources: RK860 Rev1.2 pp3-7; RK3568 AiOT reference p23; Hardware Design Guide V1.2 pp41,60.' if target=='RK3568' else 'RK860 Rev1.2 p4 supports capacitor-side sensing. RC inherited from RK3568; loop stability/values remain unqualified for RK3562.')
    ]
    for i,t in enumerate(notes):content.append(f'(text {q(t)} (at 15 {211+i*5.08} 0) (effects (font (size 1 1)) (justify left)) (uuid {q(uid("note"+str(i)))}))')
    embedded=[]
    for name in sorted(used):
        s=copy.deepcopy(symbols[name]);s[1]='Phoenix_Power:'+name;embedded.append(sx.dumps(s))
    sch=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {q(root)}) (paper "A3") (title_block (title "Phoenix G1 - CPU DVFS supply") (rev "DRAFT") (comment 1 "Not for fabrication")) (lib_symbols '+''.join(embedded)+')'+''.join(content)+')\n'
    (ROOT/f'kicad/{NAME}.kicad_sch').write_text(sch)
    (ROOT/f'kicad/{NAME}.kicad_pro').write_text(json.dumps({'meta':{'filename':NAME+'.kicad_pro','version':1}},indent=2)+'\n')
    (ROOT/'review/cpu-power-expected.json').write_text(json.dumps(contract,indent=2)+'\n')
    print(f'CPU supply draft: {len(contract)} pin/net assignments; 20 regulator ball names audited.')

if __name__=='__main__':main()
