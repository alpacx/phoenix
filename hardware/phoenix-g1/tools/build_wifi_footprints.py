#!/usr/bin/env python3
"""Manufacturer dimension transcription; no solder-process/RF qualification."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def footprint(name,body,pads):
 s=f'(footprint "{name}" (version 20241229) (generator "pcbnew") (layer "F.Cu") (attr smd)\n'
 s+='(property "Reference" "REF**" (at 0 -8) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15))))\n'
 s+=f'(property "Value" "{name}" (at 0 8) (layer "F.Fab") (effects (font (size 1 1) (thickness .15))))\n'
 w,h=body
 for layer,margin in [('F.Fab',0),('F.CrtYd',.5)]:s+=f'(fp_rect (start {-w/2-margin} {-h/2-margin}) (end {w/2+margin} {h/2+margin}) (stroke (width .05) (type default)) (fill none) (layer "{layer}"))\n'
 for n,x,y,w,h,shape in pads:s+=f'(pad "{n}" smd {shape} (at {x} {y}) (size {w} {h}) (layers "F.Cu" "F.Paste" "F.Mask"))\n'
 s+=')\n';(ROOT/f'kicad/Phoenix_Reviewed.pretty/{name}.kicad_mod').write_text(s)
 report={'name':name,'body_mm':body,'pads':[dict(number=n,x=x,y=y,width=w,height=h,shape=sh) for n,x,y,w,h,sh in pads],'status':'DOCUMENT DIMENSION TRANSCRIPTION; assembly and RF validation pending'}
 return report
reports=[];pads=[]
for i in range(11):
 pads.extend([(i+1,-5.6875,round(-4.5+.9*i,3),1.125,.5,'rect'),(i+12,round(-4.5+.9*i,3),5.6875,.5,1.125,'rect'),(i+23,5.6875,round(4.5-.9*i,3),1.125,.5,'rect'),(i+34,round(4.5-.9*i,3),-5.6875,.5,1.125,'rect')])
pads.extend([(45,-2.7,-3.6,.6,.6,'circle'),(46,-.9,-3.6,.6,.6,'circle'),(47,.9,-3.6,.6,.6,'circle')])
reports.append(footprint('AP6256_12x12_P0.9',(12,12),pads))
reports.append(footprint('Taitien_OV_5032',(5,3.2),[(1,-1.27,1.1,1.5,1.2,'rect'),(2,1.27,1.1,1.5,1.2,'rect'),(3,1.27,-1.1,1.5,1.2,'rect'),(4,-1.27,-1.1,1.5,1.2,'rect')]))
reports.append(footprint('Hirose_UFL_R_SMT_1_80',(3,3.1),[(1,0,1.525,1,1.05,'rect'),(2,-1.475,0,1.05,2.2,'rect'),(3,1.475,0,1.05,2.2,'rect')]))
reports.append(footprint('Murata_DFE201610E',(2,1.6),[(1,-.8,0,.8,1.8,'rect'),(2,.8,0,.8,1.8,'rect')]))
(ROOT/'review/wifi-footprints.json').write_text(json.dumps({'sources':['reference/wifi-ap6256.pdf p19 (printed16)','reference/wifi-clock-c5274152.pdf','reference/wifi-ufl-c88374.pdf p3','reference/wifi-inductor-c337891.pdf p5'],'footprints':reports,'holds':['U.FL top-layer copper exclusion must be implemented with RF feed exception at layout','Epson imported footprint only checked against package terminal orientation; assembly land pattern not manufacturer-qualified','Pin1 fabrication marker/silkscreen must be added after placement','PCB solder mask and stencil process not qualified']},indent=2)+'\n')
print(f'{len(reports)} footprints transcribed; layout/assembly holds retained')
