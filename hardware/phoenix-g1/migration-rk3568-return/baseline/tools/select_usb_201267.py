#!/usr/bin/env python3
"""Select 1.6mm Molex alternative without changing USB pin/net assignments."""
from schematic_builder import *

def main():
    source=ROOT/'kicad/Phoenix_Molex.kicad_sym'
    tree=sx.loads(source.read_text())
    s=fields(tree,'symbol')[0]
    old=s[1];s[1]='2012670005'
    for child in fields(s,'symbol'):child[1]=child[1].replace(old,'2012670005')
    for prop in fields(s,'property'):
        if prop[1]=='Value':prop[2]='2012670005'
        elif prop[1]=='Footprint':prop[2]='Phoenix_Reviewed:USB_C_Molex_2012670005'
        elif prop[1]=='Datasheet':prop[2]='https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/201/201267/2012670005_sd.pdf'
    (ROOT/'kicad/Phoenix_Molex_201267.kicad_sym').write_text(sx.dumps(tree)+'\n')
    p=ROOT/'sourcing/selected-references.json';d=json.loads(p.read_text())
    for code,refs in list(d.items()):
        remaining=[r for r in refs.split() if r!='J1']
        if remaining:d[code]=' '.join(remaining)
        else:del d[code]
    d['C565324']='J1';p.write_text(json.dumps(d,indent=2)+'\n')
    print('J1 candidate2012670005 selected; pin/net mapping unchanged')
if __name__=='__main__':main()
