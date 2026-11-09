#!/usr/bin/env python3
"""Candidate mixed-pitch lattice from package drawing. Land/process NOT qualified."""
import csv,json,re,math
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'migration-rk3562'
rows=list(csv.DictReader((R/'review/manufacturer-pins.csv').open()))
outer='A B C D E F G H J K L M N P R T U V W Y AA AB AC AD AE AF AG'.split()
inner='A B C D E F G H J K L M N P R'.split();pads=[]
for row in rows:
 b=row['ball'];m=re.fullmatch(r'(1?)([A-Z]+)(\d+)',b);inside=bool(m[1]);labels=inner if inside else outer;pitch=.65 if inside else .5
 col=int(m[3]);assert 1<=col<=len(labels);x=(col-(len(labels)+1)/2)*pitch;y=(labels.index(m[2])-(len(labels)-1)/2)*pitch
 pads.append({'ball':b,'x_mm':round(x,4),'y_mm':round(y,4),'land_mm':.25,'region':'inner' if inside else 'outer'})
assert len(pads)==478 and len({(p['x_mm'],p['y_mm']) for p in pads})==478
name='RK3562_FCCSP478_13.9mm_MIXED_PITCH_CANDIDATE'
s=f'(footprint "{name}" (version 20241229) (generator "pcbnew") (layer "F.Cu") (descr "UNQUALIFIED lands and assembly process; package lattice from Rockchip Rev1.2 pp16-17") (attr smd)\n'
s+='(fp_text reference "U?" (at 0 -8) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15))))\n(fp_text value "RK3562" (at 0 8) (layer "F.Fab") (effects (font (size 1 1) (thickness .15))))\n'
for layer,half,width in [('F.Fab',6.95,.1),('F.CrtYd',7.25,.05)]:s+=f'(fp_rect (start {-half} {-half}) (end {half} {half}) (stroke (width {width}) (type default)) (fill none) (layer "{layer}"))\n'
s+='(fp_circle (center -7.3 -7.3) (end -7.15 -7.3) (stroke (width .1) (type default)) (fill solid) (layer "F.SilkS"))\n'
for p in pads:s+=f'(pad "{p["ball"]}" smd circle (at {p["x_mm"]} {p["y_mm"]}) (size .25 .25) (layers "F.Cu" "F.Paste" "F.Mask"))\n'
s+=')\n';dest=R/'kicad/Phoenix_RK3562_Candidates.pretty';dest.mkdir(exist_ok=True);(dest/(name+'.kicad_mod')).write_text(s)
report={'status':'CANDIDATE LATTICE; NOT APPROVED LAND PATTERN','source':'../reference/rk3562-cost-study.pdf pp16-17 visually inspected','top_view':'A1 upper left; manufacturer bottom view mirrored across vertical axis','body_nominal_mm':[13.9,13.9],'height_nominal_max_mm':[.87,.947],'ball_nominal_range_mm':[.3,.25,.35],'land_candidate_mm':.25,'pads':pads,'holds':['Independent ball-map/coordinate crosscheck','Manufacturer land/paste recommendations and solder joint reliability','Escape routing, inner-layer drill clearance and plane return paths','Assembly DFM, ENIG requirement for0.25mm BGA lands','Do not apply a0.35/0.2mm via indiscriminately in0.5mm cells']}
(R/'review/package-candidate.json').write_text(json.dumps(report,indent=2)+'\n');print(len(pads),'candidate pads; footprint NOT assigned to assembly')
