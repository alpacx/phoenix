#!/usr/bin/env python3
"""PHY-side ESD clamp draft. Does not claim surge or system IEC compliance."""
from schematic_builder import *

def main():
    symbols = load_symbols(['TPD4EUSB30DQAR'], [])
    symbol = symbols.pop('TPD4EUSB30DQAR')
    old, new = 'TPD4EUSB30DQAR', 'TPD4E05U06DQAR'
    symbol[1] = new
    for sub in fields(symbol, 'symbol'):
        sub[1] = str(sub[1]).replace(old, new)
    for prop in fields(symbol, 'property'):
        if prop[1] in ['Value', 'Manufacturer Part']:
            prop[2] = new
        elif prop[1] == 'Datasheet':
            prop[2] = 'https://www.ti.com/lit/ds/symlink/tpd4e05u06.pdf'
        elif 'LCSC' in str(prop[1]):
            prop[2] = 'C138714'
    for pin in walk(symbol, 'pin'):
        number = str(fields(pin, 'number')[0][1])
        pin[1] = sx.Symbol('no_connect' if number in ['6','7','9','10'] else 'passive')
    # TI DQA package and pin functions match this 10-pad land pattern.
    # Pins 6/7/9/10 have no internal connection and are deliberately unused.
    symbols[new] = symbol
    save_library('Phoenix_Ethernet_ESD', symbols)
    sheet = Sheet('ethernet-esd', 'Phoenix G1 - PHY-side Ethernet ESD', 'Phoenix_Ethernet_ESD', symbols)
    for ref, pair, x in [('U22',0,88.9), ('U23',2,254.0)]:
        nets = {'1':f'ETH_MDI{pair}_P','2':f'ETH_MDI{pair}_N',
                '4':f'ETH_MDI{pair+1}_P','5':f'ETH_MDI{pair+1}_N',
                '3':'GND','8':'GND','6':None,'7':None,'9':None,'10':None}
        sheet.place(new, ref, x, 76.2, nets, mpn=new)
    notes = [
        'Two TI C138714 devices protect the eight PHY-side MDI conductors; not the isolated cable side.',
        'Place between transformer and PHY with short ground returns and no long shunt stubs.',
        'Nominal line capacitance 0.5pF; include land pattern and clamp loading in MDI layout review.',
        '5.5V stand-off is not a guarantee that the PHY survives every surge. Check residual stress experimentally.',
        'Cable-side isolation is retained. Do not move these ground-referenced clamps across the transformer.',
        'System ESD/EFT/surge performance requires finished layout and prototype tests; component rating is insufficient.',
        'Sources: TI SLVSBO7L pin table, DQA package drawing; TI system-level ESD guide SSZB130 Ethernet topology.',
    ]
    for i, note in enumerate(notes):
        sheet.note(note, 20, 150+i*8)
    sheet.save()

if __name__ == '__main__':
    main()
