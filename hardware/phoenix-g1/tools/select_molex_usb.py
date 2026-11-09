#!/usr/bin/env python3
"""Preserve the KiCad10 Molex footprint, verify key drawing dimensions, and adapt symbol.
Mechanical qualification still requires the 0.8mm board and assembly process.
"""
from schematic_builder import *
import copy,shutil

def main():
    name='USB_C_Receptacle_Molex_105450-0101'
    src=Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/Connector_USB.pretty')/(name+'.kicad_mod')
    tree=sx.loads(src.read_text());pads=fields(tree,'pad')
    assert len(pads)==28
    assert {p[1] for p in pads}=={f'{r}{n}' for r in ['A','B'] for n in range(1,13)}|{'SH'}
    shield=[p for p in pads if p[1]=='SH']
    assert sorted(tuple(fields(p,'drill')[0][2:]) for p in shield)==[(.6,1.6),(.6,1.6),(.6,2.1),(.6,2.1)]
    assert not any(str(p[2])=='np_thru_hole' for p in pads)
    for p in pads:
        if p[1]=='SH':continue
        assert abs(fields(p,'size')[0][2]-.7)<1e-9
    # JLC published pad-to-pad minimum0.15mm; drawing has0.1955mm shield/ground gap.
    # Geometry unchanged; local rule applies only to this connector, not the board.
    tree.append(sx.loads('(clearance 0.15)'))
    (ROOT/'kicad/Phoenix_Reviewed.pretty'/src.name).write_text(sx.dumps(tree)+'\n')
    lib=sx.loads((ROOT/'kicad/Import_C3197666.kicad_sym').read_text())
    symbol=copy.deepcopy(fields(lib,'symbol')[0]);old=symbol[1];symbol[1]='1054500101'
    for child in fields(symbol,'symbol'):
        child[1]=child[1].replace(old,'1054500101')
        for pin in list(fields(child,'pin')):
            num=fields(pin,'number')[0]
            if str(num[1]) in ['26','27','28']:child.remove(pin)
            elif str(num[1])=='25':num[1]='SH'
    for prop in fields(symbol,'property'):
        if prop[1]=='Value':prop[2]='1054500101'
        if prop[1]=='Footprint':prop[2]='Phoenix_Reviewed:'+name
        if prop[1]=='Datasheet':prop[2]='https://www.molex.com/pdm_docs/sd/1054500101_sd.pdf'
    (ROOT/'kicad/Phoenix_Molex.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor")'+sx.dumps(symbol)+')\n')
    report={'part':'1054500101','jlc':'C134092','footprint':'Phoenix_Reviewed:'+name,
        'source_library':'KiCad10.0.7 Connector_USB; copied without geometry modifications',
        'drawing':'Molex SD-105450-001, sheet2, release2017-04-24; manufacturer drawing mirrored at https://studfile.net/preview/18657138/',
        'manufacturer_current_series':'https://www.molex.com/en-us/products/series-chart/105450',
        'verified':['24 signal contacts plus four common shield pads','No NPTH holes','Four plated slots width0.6mm, length1.6/2.1mm','Row contact lands0.7mm long','Local clearance0.15mm per JLC pad-to-pad minimum; no exclusions','Top-layer restricted area retained'],
        'board_edge_local_y_mm':4.325,'provisional_board_thickness_mm':.8,
        'limitations':['Board stackup not qualified; manufacturer recommends0.8mm PCB for this variant.','Legacy drawing mirror used because official PDF download unavailable; current drawing must be reconciled before release.','Assembly hole/tail tolerances and solder process unqualified.']}
    (ROOT/'review/usb-connector-footprint.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Molex footprint dimensional screening PASS; manufacturing qualification pending')
if __name__=='__main__':main()
