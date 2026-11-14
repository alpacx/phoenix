"""Bounded two-signal-layer bridge with one additional through via. DRC required."""
import math
import pcbnew as p
from local_pcb_router import LocalRouter

def bridge_with_one_via(board,name,start,end,via_diameter=.45,via_drill=.2):
 bounds=(max(30,min(start[0],end[0])-5),max(.5,min(start[1],end[1])-5),min(84,max(start[0],end[0])+5),min(34,max(start[1],end[1])+5))
 r=LocalRouter(board,bounds,width=.2,grid=.1);s,g=r.cell(start),r.cell(end);layers=[p.In2_Cu,p.In3_Cu,p.B_Cu];blocked={layer:r.blocked(layer,name) for layer in layers};forbidden=set()
 for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden|=r.blocked(layer,name,via_diameter,True)
 starts={layer:r.paths_from(blocked[layer],s,80) for layer in layers}
 ends={layer:r.paths_from(blocked[layer],g,80) for layer in layers}
 for first in layers:
  for second in layers:
   if first==second:continue
   a,z=starts[first],ends[second];possible=(a['distances'].keys() & z['distances'].keys())-forbidden
   for q in sorted(possible,key=lambda q:a['distances'][q]+z['distances'][q]):
    xy=r.world(q)
    if min(math.dist(xy,start),math.dist(xy,end))<max(.65,.25+via_drill):continue
    if any(math.dist(xy,r.xy(t))<.25+via_drill/2+p.ToMM(t.GetDrillValue())/2-1e-6 for t in board.GetTracks() if isinstance(t,p.PCB_VIA)):continue
    path=[start]+r.path_from_tree(a,q)
    tail=list(reversed(r.path_from_tree(z,q)))+[end]
    return {'segments':[(first,path),(second,tail)],'via':xy}
 return None
