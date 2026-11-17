"""Bounded low-current PHY reset route; caller must run DRC and preservation."""
import math
import pcbnew as p
from local_pcb_router import LocalRouter

def add_reset_pin_route(board):
 pads={(f.GetReference(),q.GetNumber()):q for f in board.GetFootprints() for q in f.Pads()}
 a,z=pads['U5','12'],pads['R515','2'];assert a.GetNetname()==z.GetNetname()=='PHY_RESET_N'
 r=LocalRouter(board,(64,23,74,34),width=.2,grid=.025)
 assert r.xy(a)==(65.4,32.4)
 start=(66.0,32.4);path=r.solve(r.blocked(p.F_Cu,'PHY_RESET_N'),r.cell(start),r.cell(r.xy(z)))
 assert path,'No bounded PHY reset path'
 points=[r.xy(a),start]+path+[r.xy(z)];tracks=[]
 for x,y in zip(points,points[1:]):
  startp=p.VECTOR2I(*(p.FromMM(v) for v in x));endp=p.VECTOR2I(*(p.FromMM(v) for v in y))
  if startp==endp:continue
  t=p.PCB_TRACK(board);t.SetStart(startp);t.SetEnd(endp);t.SetWidth(p.FromMM(.2));t.SetLayer(p.F_Cu);t.SetNetCode(a.GetNetCode());board.Add(t);tracks.append(t)
 return {'from':'U5.12','to':'R515.2','width_mm':.2,'path_mm':points,'length_mm':sum(math.dist(x,y) for x,y in zip(points,points[1:])),'new_track_uuids':[t.m_Uuid.AsString() for t in tracks]}
