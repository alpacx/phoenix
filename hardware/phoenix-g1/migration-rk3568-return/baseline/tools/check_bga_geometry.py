#!/usr/bin/env python3
"""Compare imported BGA lattice against vendor ball-map cells.
View orientation is deliberately not inferred from an unlabelled spreadsheet.
"""
import json,re,zipfile,xml.etree.ElementTree as ET,math
from pathlib import Path
import sexpdata as sx
from audit_rk3568 import fields
ROOT=Path(__file__).resolve().parents[1];NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(ROOT/'reference/RK3568_PinOut_V1.1_20210202.xlsx') as z:
 strings=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS)]
 cells={}
 for c in ET.fromstring(z.read('xl/worksheets/sheet5.xml')).findall('.//m:c',NS):
  v=c.findtext('m:v',namespaces=NS)
  if v is not None:cells[c.get('r')]=strings[int(v)] if c.get('t')=='s' else v
cols={re.sub(r'\d','',a):int(v) for a,v in cells.items() if re.fullmatch('[A-Z]+1',a) and v.isdigit()}
rows={i:cells['A'+str(i)] for i in range(2,30)}
expected={}
for row,label in rows.items():
 for col,num in cols.items():
  val=cells.get(col+str(row))
  if val and val!='NP':expected[label+str(num)]=((num-14.5)*.65,((row-2)-13.5)*.65)
f=ROOT/'kicad/Phoenix_Reviewed.pretty/BGA-636_L19.0-W19.0-P0.65-BL.kicad_mod'
pads=fields(sx.loads(f.read_text()),'pad');actual={str(p[1]):tuple(map(float,fields(p,'at')[0][1:3])) for p in pads}
assert len(expected)==636 and set(actual)==set(expected),'Ball map / footprint inventory mismatch'
transforms=[]
for mirror in (False,True):
 for rot in range(4):
  errors=[]
  for b,(x,y) in expected.items():
   if mirror:x=-x
   for _ in range(rot):x,y=-y,x
   a=actual[b];errors.append(math.hypot(a[0]-x,a[1]-y))
  transforms.append({'rotation_deg':90*rot,'mirrored':mirror,'max_position_error_mm':max(errors)})
best=min(transforms,key=lambda a:a['max_position_error_mm'])
sizes=sorted({tuple(map(float,fields(p,'size')[0][1:3])) for p in pads})
# Conservative local channel arithmetic, not a routed-channel or SI proof.
pitch=.65;land=.35;trace=.09;clear=.09;via_land=.4;via_hole=.2
report={'status':'PASS RELATIVE LATTICE' if best['max_position_error_mm']<.01 else 'FAIL LATTICE','source':'RK3568_PinOut_V1.1 worksheet04.Ball Map; 19x19mm_0.65pitch_636Balls','footprint':str(f.relative_to(ROOT)),'checked_balls':len(expected),'best_transform_from_spreadsheet_xy':best,'pad_sizes_mm':sizes,'geometry_screen':{'pitch_mm':pitch,'land_diameter_mm':land,'between_lands_gap_mm':pitch-land,'one_90um_trace_with_two_90um_clearances_mm':trace+2*clear,'one_trace_remaining_margin_mm':round(pitch-land-trace-2*clear,6),'candidate_via_land_drill_mm':[via_land,via_hole],'alternative_via_land_drill_mm':[.35,.2],'alternative_clearance_mm':round(pitch/math.sqrt(2)-.35,6),'via_at_four_ball_cell_center_clearance_mm':round(pitch/math.sqrt(2)-(land+via_land)/2,6),'finding':'0.4mm via land between four0.35mm balls leaves about0.0846mm clearance, below0.09mm target. Do not use a generic0.4/0.2 dogbone in every cell.'},'holds':['Orientation cross-checked against datasheetV1.0 pp20-22; see bga-footprint-repair.json. Reconcile package revision before production.','Active reviewed footprint uses exact0.65mm lattice; original rounded import retained for provenance.','Pad diameter, NSMD mask/stencil and package ball size require manufacturer package drawing review.','Escape layer count, via geometry, routing clearance and impedance remain to be designed; local arithmetic is not completed routing.']}
(ROOT/'review/bga-geometry-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
