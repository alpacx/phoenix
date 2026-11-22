#!/usr/bin/env python3
"""Upstream voltage-window eFuse draft. Fast-transient protection remains unqualified."""
from schematic_builder import *

def main():
    syms=load_symbols([],['R','C'])
    symbol=fields(sx.loads((ROOT/'kicad/Import_C2653873.kicad_sym').read_text()),'symbol')[0]
    for prop in fields(symbol,'property'):prop[:]=[v for v in prop if not(isinstance(v,list) and v and str(v[0])=='id')]
    expected={str(n):v for n,v in enumerate(['DEVSLP','PGOOD','PGTH',*['OUT']*5,*['IN']*5,'EN','OVP','GND','ILIM','dVdT','IMON','~{FLT}','EP'],1)}
    assert expected=={str(fields(p,'number')[0][1]):fields(p,'name')[0][1] for p in walk(symbol,'pin')}
    for pin in walk(symbol,'pin'):
        n=int(fields(pin,'number')[0][1]);kind='input'
        if n in range(9,14) or n in [16,21]:kind='power_in'
        elif n==4:kind='power_out'
        elif n in range(5,9) or n in [17,18]:kind='passive'
        elif n in [2,20]:kind='open_collector'
        elif n==19:kind='output'
        pin[1]=sx.Symbol(kind)
    syms[symbol[1]]=symbol;save_library('Phoenix_VbusGuard',syms)
    p=ROOT/'kicad/fp-lib-table';text=p.read_text()
    if '(name "Import_C2653873")' not in text:p.write_text(text.rstrip()[:-1]+' (lib (name "Import_C2653873")(type "KiCad")(uri "${KIPRJMOD}/Import_C2653873.pretty")(options "")(descr "Imported; footprint audit pending"))\n)\n')
    sh=Sheet('usb-vbus-guard','Phoenix G1 - upstream USB voltage window','Phoenix_VbusGuard',syms)
    nets={str(n):'VBUS_PROTECTED' for n in range(4,9)}
    nets.update({str(n):'VBUS_RAW' for n in range(9,14)})
    nets.update({'1':'GND','2':None,'3':'GND','14':'VBUS_UVLO','15':'VBUS_OVP','16':'GND','17':'VBUS_GUARD_ILIM','18':'VBUS_GUARD_DVDT','19':None,'20':None,'21':'GND'})
    sh.place('TPS25940ARVCR','U24',91.44,76.2,nets,mpn='TPS25940ARVCR')
    for ref,x,y,a,b,value in [
      ('R1901',198.12,45.72,'VBUS_RAW','VBUS_UVLO','35.7k 0.1% 25ppm'),
      ('R1902',198.12,106.68,'VBUS_UVLO','GND','10k 0.1% 25ppm'),
      ('R1903',274.32,45.72,'VBUS_RAW','VBUS_OVP','47.5k 0.1% 25ppm'),
      ('R1904',274.32,106.68,'VBUS_OVP','GND','10k 0.1% 25ppm'),
      ('R1905',350.52,76.2,'VBUS_GUARD_ILIM','GND','33.2k 1%')]:
        sh.place('R',ref,x,y,{'1':a,'2':b},value,'Phoenix_Passives:R_0603_1608Metric' if ref in ['R1901','R1903','R1905'] else 'Phoenix_Passives:R_0402_1005Metric')
    for ref,x,net,value,fp in [
      ('C1901',50.8,'VBUS_RAW','1u / 25V X7R','C_0805_2012Metric'),
      ('C1902',152.4,'VBUS_PROTECTED','1u / 25V X7R','C_0805_2012Metric'),
      ('C1903',254,'VBUS_GUARD_DVDT','1n / C0G','C_0402_1005Metric')]:
        sh.place('C',ref,x,187.96,{'1':net,'2':'GND'},value,'Phoenix_Passives:'+fp)
    notes=['U24 precedes all USB-controller/AON supplies. U15 still admits main load only with Type-C 3A.',
      'UVLO nominal rising4.524V; OVP nominal rising5.6925V. Include +/-2% comparator and divider leakage/tolerance.',
      '33.2k ILIM: 2.681A nominal; no guaranteed selectivity with downstream U15. Check hot loss and load budget.',
      '1nF dVdT gives about0.42ms nominal rise to5V; downstream AON supervisor retains startup delay.',
      'DEVSLP grounded. Unused PGTH grounded; open-drain diagnostics and IMON intentionally unused.',
      'This is a voltage cut-off, not a 5.5V regulator or a validated transient clamp. TVS and dynamic overshoot remain open.',
      'USB raw input stays5V-only; no PD. Do not claim protection against arbitrary20V or IEC ESD until tested.',
      'Source: TI TPS25940 SLVSCF3A pin table/electrical limits. Imported package still requires dimensional review.']
    for i,n in enumerate(notes):sh.note(n,15,222+7*i)
    sh.save()
if __name__=='__main__':main()
