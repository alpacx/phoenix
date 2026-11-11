#!/usr/bin/env python3
"""AP6256 32.768 kHz signal routing only; oscillator supply and timing unqualified."""
import argparse,hashlib,json,math
from pathlib import Path
import pcbnew as p
from local_pcb_router import LocalRouter
ap=argparse.ArgumentParser(description=__doc__)
for k in ('input','output','report'):ap.add_argument('--'+k,type=Path,required=True)
ap.add_argument('--load-only',action='store_true',help='Preserve existing oscillator/source trace; route only series resistor to module')
ap.add_argument('--auto-bounds',action='store_true')
a=ap.parse_args();assert a.input.resolve()!=a.output.resolve()
b=p.LoadBoard(str(a.input));b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
assert all(not b.GetConnectivity().GetConnectedTracks(pads['R2003',n]) for n in (('2',) if a.load_only else ('1','2')))
def point(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
def add(path,name,layer):
 total=0
 for x,z in zip(path,path[1:]):
  if math.dist(x,z)<1e-6:continue
  t=p.PCB_TRACK(b);t.SetStart(point(x));t.SetEnd(point(z));t.SetLayer(layer);t.SetWidth(p.FromMM(.2));t.SetNetCode(b.FindNet(name).GetNetCode());b.Add(t);total+=math.dist(x,z)
 return total
bounds=(35,15,60,30)
if a.auto_bounds:
 anchors=[pads[k].GetPosition() for k in [('Y2001','3'),('R2003','1'),('R2003','2'),('U25','24')]];xs=[p.ToMM(q.x) for q in anchors];ys=[p.ToMM(q.y) for q in anchors]
 bounds=(max(1,min(xs)-3),max(1,min(ys)-3),min(89,max(xs)+3),min(39,max(ys)+3))
r=LocalRouter(b,bounds,width=.2)
x,z=pads['Y2001','3'],pads['R2003','1'];name='WIFI_LPO_SRC'
source_length=0
if not a.load_only:
 path=r.solve(r.blocked(p.F_Cu,name),r.cell(r.xy(x)),r.cell(r.xy(z)));assert path,'No source clock trace'
 source_length=add([r.xy(x)]+path+[r.xy(z)],name,p.F_Cu)
name='WIFI_LPO';middle=r.blocked(p.In2_Cu,name);forbidden=set()
for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu):forbidden |= r.blocked(layer,name,.45,True)
def sites(pad,layer):
 start=r.cell(r.xy(pad));blocked=r.blocked(layer,name);result=[]
 options={(start[0]+dx,start[1]+dy) for dx in range(-80,81,2) for dy in range(-80,81,2)}
 for q in sorted(options,key=lambda q:math.dist(q,start)):
  if not r.within(q) or q in forbidden or q in middle:continue
  path=r.solve(blocked,start,q)
  if path and sum(math.dist(a,z) for a,z in zip(path,path[1:]))<6:
   result.append((q,[r.xy(pad)]+path))
   if len(result)==30:break
 return result
starts,goals=sites(pads['R2003','2'],p.F_Cu),sites(pads['U25','24'],p.B_Cu)
print('Clock via candidates',len(starts),len(goals),flush=True)
selected=None
for qa,pa in starts:
 for qz,pz in goals:
  if math.dist(r.world(qa),r.world(qz))<.45:continue
  path=r.solve(middle,qa,qz)
  if path:selected=qa,pa,qz,pz,path;break
 if selected:break
assert selected,'No legal local clock fanouts and inner path'
qa,pa,qz,pz,path=selected
lengths=[add(pa,name,p.F_Cu),add(path,name,p.In2_Cu),add(pz,name,p.B_Cu)]
for q in (qa,qz):
 v=p.PCB_VIA(b);v.SetPosition(point(r.world(q)));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.FindNet(name).GetNetCode());b.Add(v)
ground_vias=[]
def ground_tracks(net,width,path,layer=p.F_Cu):
 assert net=='GND' and width==.2
 add(path,net,layer)
def ground_via(net,q):
 v=p.PCB_VIA(b);v.SetPosition(point(q));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.FindNet(net).GetNetCode());b.Add(v);ground_vias.append(q)
if not a.load_only:r.ground_escape(pads['Y2001','2'],ground_tracks,ground_via)
p.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();p.SaveBoard(str(a.output),b)
a.report.write_text(json.dumps({'status':'CANDIDATE CLOCK SIGNAL COPPER; NOT A WORKING CLOCK SOURCE','pcb_sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'source_net_length_mm':None if a.load_only else round(source_length,4),'existing_source_route_preserved':a.load_only,'load_net_segment_lengths_mm':dict(zip(['F.Cu','In2.Cu','B.Cu'],[round(n,4) for n in lengths])),'via_xy_mm':[r.world(qa),r.world(qz)],'added_oscillator_ground_vias_xy_mm':ground_vias,'trace_width_mm':.2,'via_land_drill_mm':[.45,.2],'limitations':['Oscillator power and bypass remain incomplete; source ground continuity is checked separately.','Accuracy, jitter, startup, edge integrity and module timing have not been measured.','No simulation or physical test; no operational Wi-Fi claim.'],'production_ready':False},indent=2)+'\n')
