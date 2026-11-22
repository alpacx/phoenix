#!/usr/bin/env python3
"""Conservative check that new via copper/mask does not overlap component pad boxes."""
import pcbnew as p,json,os,math
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel'
s=p.LoadBoard(str(D/os.environ.get('PHOENIX_SCREEN_BASELINE','baseline/source.kicad_pcb')));b=p.LoadBoard(str(D/os.environ.get('PHOENIX_SCREEN_BOARD','right-ground-vias.kicad_pcb')));old={t.m_Uuid.AsString() for t in s.GetTracks()};records=[]
for v in b.GetTracks():
 if not isinstance(v,p.PCB_VIA) or v.m_Uuid.AsString() in old:continue
 x,y=p.ToMM(v.GetPosition().x),p.ToMM(v.GetPosition().y);radius=p.ToMM(v.GetWidth(p.F_Cu))/2;nearest=None
 for f in b.GetFootprints():
  for q in f.Pads():
   for layer in [p.F_Cu,p.B_Cu]:
    if not q.IsOnLayer(layer):continue
    r=q.GetBoundingBox(layer);dx=max(p.ToMM(r.GetX())-x,0,x-p.ToMM(r.GetRight()));dy=max(p.ToMM(r.GetY())-y,0,y-p.ToMM(r.GetBottom()));gap=math.hypot(dx,dy)-radius
    if nearest is None or gap<nearest['copper_gap_mm']:nearest={'pad':f.GetReference()+'.'+q.GetNumber(),'copper_gap_mm':gap}
 records.append({'via':v.m_Uuid.AsString(),'xy_mm':[x,y],'nearest_pad_box':nearest})
print([x for x in records if x['nearest_pad_box']['copper_gap_mm']<=.05],flush=True)
assert all(x['nearest_pad_box']['copper_gap_mm']>.05 for x in records), 'New via touches component pad or 0.05 mm local margin'
r={'board':str(D/os.environ.get('PHOENIX_SCREEN_BOARD','right-ground-vias.kicad_pcb')),'baseline':str(D/os.environ.get('PHOENIX_SCREEN_BASELINE','baseline/source.kicad_pcb')),'checked_new_vias':len(records),'passed':True,'conservative_minimum_gap_mm':min(x['nearest_pad_box']['copper_gap_mm'] for x in records),'checks':records,'qualification':'Bounding-box geometric screen, not final soldermask/assembly qualification'}
(D/'new-via-pad-screen.json').write_text(json.dumps(r,indent=2)+'\n');print({k:v for k,v in r.items() if k!='checks'},flush=True);os._exit(0)
