#!/usr/bin/env python3
"""Amphenol C12401598 rev4 sheet2 land pattern, millimetres.

Original EasyEDA import is preserved. Manufacturer datum C is y=-3.27 here;
the origin matches the imported terminal row for comparison, not its flawed holes.
"""
from schematic_builder import *

def main():
    name='USB_C_Amphenol_12401598E4_2A'
    body=[f'(footprint "{name}" (version 20250108) (generator "pcbnew") (layer "F.Cu")',
          '(attr smd)', '(descr "Amphenol C12401598 rev4 sheet2; footprint draft checked against dimensions")',
          '(property "Reference" "J?" (at 0 -6) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15))))',
          '(property "Value" "12401598E4#2A" (at 0 8) (layer "F.Fab") (effects (font (size 1 1) (thickness .15))))']
    pads=[]
    def pad(number,kind,shape,x,y,w,h,drill=None):
        copper='"F.Cu" "F.Paste" "F.Mask"' if kind=='smd' else '"*.Cu" "*.Mask"'
        hole='' if drill is None else (f'(drill {drill})' if isinstance(drill,float) else f'(drill oval {drill[0]} {drill[1]})')
        body.append(f'(pad "{number}" {kind} {shape} (at {x} {y}) (size {w} {h}) {hole} (layers {copper}))')
        pads.append({'number':number,'kind':kind,'xy':[x,y],'size':[w,h],'drill':drill})
    for n in range(1,13):
        pad('A'+str(n),'smd','rect',round(-2.75+(n-1)*.5,3),-3.93,.3,.7)
        pad('B'+str(n),'smd','rect',round(2.5-(n-1)*.5,3),-2.23,.3,.7)
    # Four identical straight plated slots: copper .8x1.4, drill .5x1.1.
    for num,x,y in [('25',-4.13,-2.02),('28',4.13,-2.02),('26',-4.49,3.93),('27',4.49,3.93)]:
        pad(num,'thru_hole','oval',x,y,.8,1.4,(.5,1.1))
    pad('','np_thru_hole','circle',-3.6,-3.27,.65,.65,.65)
    pad('','np_thru_hole','oval',3.6,-3.27,.95,.65,(.95,.65))
    def rect(x1,y1,x2,y2,layer,width):
        body.append(f'(fp_rect (start {x1} {y1}) (end {x2} {y2}) (stroke (width {width}) (type default)) (fill none) (layer "{layer}"))')
    rect(-4.6,-4.18,4.6,6.32,'F.Fab',.1)
    rect(-5.15,-4.55,5.15,6.6,'F.CrtYd',.05)
    for x in [-4.72,4.72]:
        body.append(f'(fp_line (start {x} -.9) (end {x} 2.9) (stroke (width .12) (type default)) (layer "F.SilkS"))')
    # Manufacturer hatched keepout on connector-mounted layer: width7.5, length6.8.
    body.append('(zone (net 0) (net_name "") (layer "F.Cu") (hatch edge .5) (connect_pads (clearance 0)) (min_thickness .25) (keepout (tracks not_allowed) (vias not_allowed) (pads not_allowed) (copperpour not_allowed) (footprints not_allowed)) (polygon (pts (xy -3.75 -1.32) (xy 3.75 -1.32) (xy 3.75 5.48) (xy -3.75 5.48))))')
    body.append(')')
    out=ROOT/'kicad/Phoenix_Reviewed.pretty';out.mkdir(exist_ok=True)
    (out/(name+'.kicad_mod')).write_text('\n'.join(body)+'\n')
    report={'part':'12401598E4#2A','jlc':'C3197666','source':'reference/usb-connector-C3197666.pdf',
            'drawing':'C12401598 revision4 sheet2','footprint':'Phoenix_Reviewed:'+name,
            'source_datum_C_y_mm':-3.27,'recommended_board_edge_y_mm':5.48,
            'changes_from_import':['Corrected .55x1.15 drills to .5x1.1 and1x1.6 copper to.8x1.4.',
                                   'Replaced plated locating hole with.65NPTH; added missing.95x.65NPTH slot.',
                                   'Added7.5x6.8mm top-layer keepout and courtyard covering all pads.'],
            'pads':pads,'release_status':'Dimensions transcribed; DRC/assembly/enclosure checks required.'}
    (ROOT/'review/usb-connector-footprint.json').write_text(json.dumps(report,indent=2)+'\n')
    print(name,len(pads),'pads including two mechanical holes')

if __name__=='__main__':main()
