#!/usr/bin/env python3
"""Read-only bounding-box screen. NOT packing, routing or enclosure validation."""
import json,hashlib
from pathlib import Path
import pcbnew as p
R=Path(__file__).resolve().parents[1];B=R/'migration-rk3562/experiments/lpddr4-1gb';O=R/'migration-rk3562/experiments/emmc-8gb'
cp=json.loads((B/'working-board.json').read_text());source=B/cp['board'];assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(source));items=[]
for f in b.GetFootprints():
 box=f.GetBoundingBox(False,False)
 items.append({'ref':f.GetReference(),'side':f.GetLayerName(),'through_holes':any(pad.GetDrillSize().x>0 for pad in f.Pads()),'box':[p.ToMM(x) for x in (box.GetX(),box.GetY(),box.GetRight(),box.GetBottom())]})
def overlaps(a,c):return a[0]<c[2] and a[2]>c[0] and a[1]<c[3] and a[3]>c[1]
candidates=[]
for side in ['F.Cu','B.Cu']:
 options=[]
 for rotate in [False,True]:
  w,h=(13.6,12.1) if rotate else (12.1,13.6)
  for x in range(7,78):
   for y in range(7,29):
    box=[x-w/2,y-h/2,x+w/2,y+h/2]
    if box[0]<.5 or box[1]<.5 or box[2]>84.5 or box[3]>34.5:continue
    hits=[a['ref'] for a in items if (a['side']==side or a['through_holes']) and overlaps(box,a['box'])]
    options.append({'side':side,'center_mm':[x,y],'rotation_degrees':90 if rotate else 0,'overlapping_refs':hits,'count':len(hits)})
 options.sort(key=lambda a:a['count']);candidates+=options[:5]
report={'status':'COMPONENT_BODY_SCREEN_ONLY','target_mm':[85,35],'source_outline_mm':[90,40],'package_courtyard_candidate_mm':[12.1,13.6],'positions_with_fewest_same_side_body_conflicts':candidates,'limits':['Existing component positions preserved for screening only; other components may lie outside target','Through-hole footprints conservatively block their entire bounding box on both sides; no copper/via/other opposite-side height or heat-spreader clearance check','Support parts need additional placement area','No signal escape or power-plane feasibility established'],'assembly_ready':False}
(O/'review/85x35-body-screen.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
