#!/usr/bin/env python3
"""Correct RK3568 grid rounding without changing pad assignment/orientation.
Package views: Rockchip datasheet V1.0 pp20-22 (Radxa copy).
Pad land, mask and paste qualification remains separate.
"""
from schematic_builder import *
import re
name='BGA-636_L19.0-W19.0-P0.65-BL'
src=ROOT/f'kicad/Phoenix_Candidates.pretty/{name}.kicad_mod'
fp=sx.loads(src.read_text());rows='A B C D E F G H J K L M N P R T U V W Y AA AB AC AD AE AF AG AH'.split()
for pad in fields(fp,'pad'):
 ball=str(pad[1]);m=re.fullmatch(r'([A-Z]+)([0-9]+)',ball);assert m,ball
 # Imported orientation is 270 degrees from manufacturer's top-view ball map.
 xy=[round((rows.index(m[1])-13.5)*.65,3),round((14.5-int(m[2]))*.65,3)]
 old=fields(pad,'at')[0][1:3];assert max(abs(float(a)-b) for a,b in zip(old,xy))<=.00501
 fields(pad,'at')[0][1:3]=xy
# Do not alter the existing A1 chamfer at bottom-left.
for layer,half in [('F.Fab',9.575),('F.CrtYd',9.85)]:
 for a,b in [((-half,-half),(half,-half)),((half,-half),(half,half)),((half,half),(-half,half)),((-half,half),(-half,-half))]:
  fp.append(sx.loads(f'(fp_line (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (layer {layer}) (width 0.05))'))
(ROOT/f'kicad/Phoenix_Reviewed.pretty/{name}.kicad_mod').write_text(sx.dumps(fp)+'\n')
(ROOT/'review/bga-footprint-repair.json').write_text(json.dumps({'source':str(src.relative_to(ROOT)),'output':'Phoenix_Reviewed:'+name,'changes':['Exact0.65mm grid; maximum5um per-axis correction of import rounding.','Fab outline uses19.15mm maximum body; courtyard19.7mm is a placement allowance, not an assembly approval.'],'orientation_evidence':'Datasheet Fig2-2 TOP VIEW A1 upper-left, Fig2-3 BOTTOM VIEW A1 lower-left, columns1..28 left-to-right. Worksheet04.Ball Map is consistent with top view. Active footprint rotates this270degrees: A1 lower-left, A28 upper-left, AH1 lower-right; no reflection.','package_dimensions_mm':{'body_max':19.15,'ball_grid_span':17.55,'pitch':.65,'ball_diameter_min_nom_max':[.31,.36,.41],'package_height_min_nom_max':[1.36,1.52,1.68]},'holds':['Package source is early V1.0; reconcile with actual ordered silicon/package revision.','Copper land0.35mm retained as draft; NSMD/mask, paste, solder assembly and BGA escape not qualified.']},indent=2)+'\n')
print('636 pad coordinates corrected; package orientation documented; assembly not qualified')
