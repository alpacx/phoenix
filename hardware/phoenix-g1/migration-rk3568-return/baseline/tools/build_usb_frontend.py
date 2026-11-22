#!/usr/bin/env python3
"""Build a reviewable USB-C data frontend; NOT a complete gateway design.

Dependencies: sexpdata. Passive MPNs and connector land pattern still need review.
Power input, sequencing, discharge and current gating belong to a separate circuit.
"""
import copy
import json
import math
import shutil
import uuid
from pathlib import Path
import sexpdata as sx

ROOT = Path(__file__).resolve().parents[1]
def uid(name): return str(uuid.uuid5(uuid.NAMESPACE_URL, 'phoenix-g1/usb/' + name))
def q(s): return json.dumps(str(s))
def tagged(node, key):
    return [e for e in node if isinstance(e, list) and e and str(e[0]) == key]
def walk(node, key):
    if isinstance(node, list):
        if node and str(node[0]) == key: yield node
        for e in node: yield from walk(e, key)

def main():
    lib = sx.loads((ROOT/'kicad/Phoenix_Candidates.kicad_sym').read_text())
    device = sx.loads(Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/Device.kicad_sym').read_text())
    symbols = {n[1]: n for n in tagged(lib, 'symbol')}
    symbols.update({n[1]: n for n in tagged(device, 'symbol') if n[1] in ('R','C')})
    # Imported symbols use 'unspecified' everywhere. Set electrical types from
    # TI pin-function tables, not by suppressing ERC warnings.
    imported = sx.loads((ROOT/'kicad/Phoenix_Molex_201267.kicad_sym').read_text())
    symbols.update({n[1]:n for n in tagged(imported,'symbol')})
    for prop in tagged(symbols['2012670005'],'property'):
        if prop[1]=='Footprint':prop[2]='Phoenix_Reviewed:USB_C_Molex_2012670005'
    selected = ['2012670005','HD3SS3220IRNHR','TPD4EUSB30DQAR','R','C']
    qualified=[]
    for name in selected:
        symbol=symbols[name]
        for prop in tagged(symbol,'property'):
            prop[:] = [e for e in prop if not(isinstance(e,list) and e and str(e[0])=='id')]
        for pin in walk(symbol,'pin'):
            num=str(tagged(pin,'number')[0][1])
            kind='passive'
            if name=='HD3SS3220IRNHR':
                if num in ('1','2'): kind='bidirectional'
                elif num in ('8','13','28','30','31'): kind='power_in'
                elif num in ('3','4','5','12','22','29'): kind='input'
                elif num in ('11','23','24','25','26','27'): kind='open_collector'
            if name=='TPD4EUSB30DQAR' and num in ('6','7','9','10'): kind='no_connect'
            if name not in ('R','C'): pin[1]=sx.Symbol(kind)
        qualified.append(sx.dumps(symbol))
    (ROOT/'kicad/Phoenix_USB.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor")'+''.join(qualified)+')\n')
    fpdir=ROOT/'kicad/Phoenix_Passives.pretty'; fpdir.mkdir(exist_ok=True)
    for library,footprint in [('Resistor_SMD','R_0402_1005Metric'),('Capacitor_SMD','C_0402_1005Metric')]:
        shutil.copyfile(Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')/(library+'.pretty')/(footprint+'.kicad_mod'),fpdir/(footprint+'.kicad_mod'))
    root = uid('root')
    placed, content, contract = [], [], []
    def place(name, ref, x, y, nets, value=None):
        symbol = symbols[name]
        prefix = 'Phoenix_USB'
        libid = prefix + ':' + name
        pins = list(walk(symbol,'pin'))
        pinids = {str(tagged(p,'number')[0][1]) for p in pins}
        assert pinids == set(nets), (ref, pinids-set(nets), set(nets)-pinids)
        props = {p[1]:p[2] for p in tagged(symbol,'property')}
        fp = props.get('Footprint','')
        if name in ('R','C'):
            fp = 'Phoenix_Passives:R_0402_1005Metric' if name == 'R' else 'Phoenix_Passives:C_0402_1005Metric'
        if ref in ['R601','R605','R606']: fp='Phoenix_Passives:R_0603_1608Metric'
        top = max(tagged(p,'at')[0][2] for p in pins)
        body = f'(symbol (lib_id {q(libid)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {q(uid(ref))})'
        field_x=x+13 if name in ('R','C','2012670005') else x
        for key, val, yy, hidden in [('Reference',ref,y-top-10,False),('Value',value or name,y-top-7.5,False),('Footprint',fp,y,True),('Qualification','DRAFT - not released',y,True),('MPN',name if name not in ('R','C') else 'UNQUALIFIED',y,True)]:
            body += f'(property {q(key)} {q(val)} (at {field_x} {yy} 0) (effects (font (size 1 1))'+(' hide' if hidden else '')+'))'
        body += f'(instances (project "usb-c-frontend" (path {q("/"+root)} (reference {q(ref)}) (unit 1)))))'
        content.append(body)
        for p in pins:
            num = str(tagged(p,'number')[0][1]); net = nets[num]
            px, py, angle = tagged(p,'at')[0][1:]
            px, py = round(x+px,4), round(y-py,4)
            contract.append({'ref':ref,'pin':num,'pin_name':tagged(p,'name')[0][1],'net':net})
            if net is None:
                content.append(f'(no_connect (at {px} {py}) (uuid {q(uid(ref+num+"nc"))}))')
                continue
            # Pins point toward the body; extend wires outwards.
            ex = round(px-5.08*math.cos(math.radians(angle)),4)
            ey = round(py+5.08*math.sin(math.radians(angle)),4)
            content.append(f'(wire (pts (xy {px} {py}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid {q(uid(ref+num+"wire"))}))')
            a = 90 if angle in (90,270) else 0
            justify = 'right' if angle in (0,90) else 'left'
            content.append(f'(label {q(net)} (at {ex} {ey} {a}) (effects (font (size 0.95 0.95)) (justify {justify} bottom)) (uuid {q(uid(ref+num+"label"))}))')
        placed.append(libid)
    port = {'A1':'GND','A2':'USB_TX1_P','A3':'USB_TX1_N','A4':'VBUS_RAW','A5':'USB_CC1','A6':'USB_DP','A7':'USB_DM','A8':None,'A9':'VBUS_RAW','A10':'USB_RX2_N','A11':'USB_RX2_P','A12':'GND',
        'B1':'GND','B2':'USB_TX2_P','B3':'USB_TX2_N','B4':'VBUS_RAW','B5':'USB_CC2','B6':'USB_DP','B7':'USB_DM','B8':None,'B9':'VBUS_RAW','B10':'USB_RX1_N','B11':'USB_RX1_P','B12':'GND','SH':'USB_SHIELD'}
    place('2012670005','J1',57.15,63.5,port)
    place('HD3SS3220IRNHR','U6',196.85,63.5,{
        '1':'USB_CC2','2':'USB_CC1','3':'GND','4':'GND','5':'CC_VBUS_SENSE',
        '6':'SOC_USB_TX_P','7':'SOC_USB_TX_N','8':'+3V3_AON','9':'SOC_USB_RX_P','10':'SOC_USB_RX_N',
        '11':'USB_ORIENTATION','12':'USB_MUX_ENABLE_N','13':'GND','14':'USB_RX1_N','15':'USB_RX1_P',
        '16':'MUX_TX1_N','17':'MUX_TX1_P','18':'USB_RX2_N','19':'USB_RX2_P','20':'MUX_TX2_N','21':'MUX_TX2_P',
        '22':None,'23':None,'24':None,'25':'CC_OUT1_N','26':'CC_OUT2_N','27':None,'28':'GND',
        '29':'USB_CC_ENABLE_N','30':'VBUS_PROTECTED','31':'GND'})
    for ref,x,y,lines in [('U7',57.15,125.73,['USB_TX1_P','USB_TX1_N','USB_RX1_P','USB_RX1_N']),
                         ('U8',196.85,125.73,['USB_TX2_P','USB_TX2_N','USB_RX2_P','USB_RX2_N']),
                         ('U9',336.55,125.73,['USB_DP','USB_DM','USB_CC1','USB_CC2'])]:
        nets = dict(zip(['1','2','4','5'],lines)); nets.update({'3':'GND','8':'GND','6':None,'7':None,'9':None,'10':None})
        place('TPD4EUSB30DQAR',ref,x,y,nets)
    for i,(a,b) in enumerate([('MUX_TX1_P','USB_TX1_P'),('MUX_TX1_N','USB_TX1_N'),('MUX_TX2_P','USB_TX2_P'),('MUX_TX2_N','USB_TX2_N')]):
        place('C',f'C{601+i}',38.1+38.1*i,177.8,{'1':a,'2':b},'100n / 16V X7R')
    for ref,x,a,b,value in [('R602',279.4,'+3V3_AON','USB_ORIENTATION','200k 1%'),('R603',330.2,'+3V3_AON','CC_OUT1_N','200k 1%'),('R604',381,'+3V3_AON','CC_OUT2_N','200k 1%')]:
        place('R',ref,x,177.8,{'1':a,'2':b},value)
    for ref,x,a,b in [('R601',228.6,'VBUS_PROTECTED','CC_VBUS_SERIES_1'),('R605',279.4,'CC_VBUS_SERIES_1','CC_VBUS_SERIES_2'),('R606',330.2,'CC_VBUS_SERIES_2','CC_VBUS_SENSE')]:
        place('R',ref,x,198.12,{'1':a,'2':b},'300k 0.1% 25ppm')
    place('C','C605',330.2,63.5,{'1':'VBUS_PROTECTED','2':'GND'},'100n / 16V X7R')
    place('C','C606',381,63.5,{'1':'+3V3_AON','2':'GND'},'100n / 10V X7R')
    embedded=[]
    for libid in sorted(set(placed)):
        name=libid.split(':',1)[1]; symbol=copy.deepcopy(symbols[name]); symbol[1]=libid
        for prop in tagged(symbol,'property'):
            prop[:] = [e for e in prop if not(isinstance(e,list) and e and str(e[0])=='id')]
        embedded.append(sx.dumps(symbol))
    notes=[
        'USB-C DATA FRONTEND - ENGINEERING DRAFT, NOT FOR FABRICATION',
        'Sink/UFP only, GPIO mode: PORT=GND, ADDR=NC. No USB Power Delivery negotiation.',
        'R601+R605+R606 = 900k series sense resistance; three stocked 300k 0.1%/25ppm parts.',
        'Require CC_OUT1_N=0 AND CC_OUT2_N=0 for the proposed 3 A startup policy; OUT2 alone is insufficient.',
        'USB_CC_ENABLE_N requires verified VDD5/VCC33 sequencing (TI section 6.3.12, >=2 ms when controlled).',
        'USB_MUX_ENABLE_N must default disabled until main SoC supplies are valid.',
        'TX AC coupling is on the connector side of the mux, following TI UFP reference. No duplicate SoC TX capacitors.',
        'USB_SHIELD termination and connector footprint remain to validate. Passive MPNs are not selected.',
        'RK3568 endpoints: T28/T27 TX+/-; R28/R27 RX+/-; P27/P28 DP/DM; M24 VBUSDET needs its own sensing circuit.',
        'Sources: TI HD3SS3220 SLLSES1E, TPD4EUSB30 SLVSAC2G; Rockchip Hardware Design Guide V1.2.'
    ]
    for i,t in enumerate(notes):
        content.append(f'(text {q(t)} (at 15 {220+i*5.08} 0) (effects (font (size 1.1 1.1)) (justify left)) (uuid {q(uid("note"+str(i)))}))')
    result=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {q(root)}) (paper "A3") (title_block (title "Phoenix G1 - USB-C data frontend") (rev "DRAFT") (comment 1 "Incomplete system - not for manufacture")) (lib_symbols '+''.join(embedded)+')'+''.join(content)+')\n'
    (ROOT/'kicad/usb-c-frontend.kicad_sch').write_text(result)
    (ROOT/'review/usb-c-frontend-expected.json').write_text(json.dumps(contract,indent=2)+'\n')
    print(f'Wrote USB frontend: {len(placed)} components; {len(contract)} pin dispositions. System remains incomplete.')

if __name__ == '__main__': main()
