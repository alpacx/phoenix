"""Screen R530 departures with the full trace width against actual front copper."""
import json, math, os
from pathlib import Path
import pcbnew as p
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel/runs/input-ground-local-002'
board=p.LoadBoard(str(root/'phy-joint.kicad_pcb'))
origin=p.VECTOR2I(p.FromMM(53.51),p.FromMM(27))
obs=[t for t in board.GetTracks() if t.IsOnLayer(p.F_Cu) and t.GetNetname()!='+3V3_PHY']
obs.extend(q for f in board.GetFootprints() for q in f.Pads() if q.IsOnLayer(p.F_Cu) and q.GetNetname()!='+3V3_PHY')
probe=p.PCB_TRACK(board);probe.SetStart(origin);probe.SetEnd(origin);probe.SetWidth(p.FromMM(1.05));probe.SetLayer(p.F_Cu)
origin_blockers=[{'net':o.GetNetname(),'uuid':o.m_Uuid.AsString(),'item':o.GetClass()} for o in obs if probe.GetEffectiveShape(p.F_Cu).Collide(o.GetEffectiveShape(p.F_Cu),p.FromMM(.2))]
obs=[o.GetEffectiveShape(p.F_Cu) for o in obs if o.GetBoundingBox().Inflate(p.FromMM(4)).Contains(origin)]
found=[]
for dx in (0,.05,.10,.15):
 for dy in (0,.05,.10,-.05,-.10):
  start=origin+p.VECTOR2I(p.FromMM(dx),p.FromMM(dy))
  for deg in range(0,360,5):
   angle=math.radians(deg)
   for dist in (2,1.5,1,.75,.5):
    end=start+p.VECTOR2I(p.FromMM(dist*math.cos(angle)),p.FromMM(dist*math.sin(angle)))
    track=p.PCB_TRACK(board);track.SetStart(start);track.SetEnd(end);track.SetWidth(p.FromMM(1.05));track.SetLayer(p.F_Cu)
    shape=track.GetEffectiveShape(p.F_Cu)
    if all(not shape.Collide(o,p.FromMM(.2)) for o in obs):
     found.append([dx,dy,deg,dist]);break
(root/'r530-departures.json').write_text(json.dumps(dict(origin_blockers=origin_blockers,width_mm=1.05,clearance_mm=.2,offset_x_y_angle_deg_length_mm=found,scope='front tracks vias and pads only; not a complete feed or DRC'),indent=2)+'\n')
print(len(found),sorted(found,key=lambda v:-v[-1])[:4],flush=True);os._exit(0)
