import pcbnew as p,json,os
from pathlib import Path
D=Path('hardware/phoenix-g1/migration-rk3562/experiments/phy-power-parallel');b=p.LoadBoard(str(D/'runs/joint-002/phy-joint.kicad_pcb'));out={'pads':[],'tracks':[]}
for f in b.GetFootprints():
 for q in f.Pads():
  if not q.IsOnLayer(p.F_Cu):continue
  z=q.GetBoundingBox(p.F_Cu);x,y,w,h=[p.ToMM(v) for v in [z.GetX(),z.GetY(),z.GetWidth(),z.GetHeight()]]
  if x+w<50 or x>69 or y+h<20 or y>35:continue
  out['pads'].append([x,y,w,h,f.GetReference(),q.GetNetname()])
for t in b.GetTracks():
 if not t.IsOnLayer(p.F_Cu):continue
 a=[p.ToMM(v) for v in t.GetStart()];z=[p.ToMM(v) for v in t.GetEnd()]
 if max(a[0],z[0])<50 or min(a[0],z[0])>69 or max(a[1],z[1])<20 or min(a[1],z[1])>35:continue
 out['tracks'].append([a,z,p.ToMM(t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth()),t.GetNetname()])
(D/'map.json').write_text(json.dumps(out));os._exit(0)
