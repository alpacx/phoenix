#!/usr/bin/env python3
"""Restore PMIC IO and LPO supply in relocation experiment; geometry/continuity only."""
import argparse,json,hashlib,math
from pathlib import Path
import pcbnew as p
from local_pcb_router import LocalRouter
ap=argparse.ArgumentParser(description=__doc__)
for k in ('input','output','report'):ap.add_argument('--'+k,type=Path,required=True)
a=ap.parse_args();assert a.input.resolve()!=a.output.resolve();b=p.LoadBoard(str(a.input));b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};name='+3V3_IO';code=b.FindNet(name).GetNetCode();bounds=(45,2,68,34);records=[]
def pt(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
def xy(item):return p.ToMM(item.GetPosition().x),p.ToMM(item.GetPosition().y)
def add(path,width,layer):
 for x,z in zip(path,path[1:]):
  if math.dist(x,z)<1e-6:continue
  t=p.PCB_TRACK(b);t.SetStart(pt(x));t.SetEnd(pt(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(code);b.Add(t)
def via(q):
 v=p.PCB_VIA(b);v.SetPosition(pt(q));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(code);b.Add(v);return v
assert math.dist(xy(pads['U4','55']),(61.75,5.59))<.001
assert not b.GetConnectivity().GetConnectedTracks(pads['U4','55'])
add([(61.75,5.59),(61.75,4.65)],.127,p.F_Cu);root=via((61.75,4.65));roots=[root]
for key in [('R530','1'),('C2004','1'),('C2007','1'),('Y2001','1'),('Y2001','4')]:
 pad=pads[key];assert pad.GetNetname()==name;b.BuildConnectivity();conn=b.GetConnectivity();connected={q.m_Uuid.AsString() for q in conn.GetConnectedItems(root)};connected.add(root.m_Uuid.AsString())
 if pad.m_Uuid.AsString() in connected:continue
 layer=p.F_Cu if pad.IsOnLayer(p.F_Cu) else p.B_Cu;r=LocalRouter(b,bounds,width=.2);blocked=r.blocked(layer,name);start=r.cell(xy(pad));done=False
 sources=[q for q in pads.values() if q.GetNetname()==name and q.IsOnLayer(layer) and q.m_Uuid.AsString() in connected]+roots
 for source in sorted(sources,key=lambda q:math.dist(xy(q),xy(pad))):
  if math.dist(xy(source),xy(pad))>6:continue
  path=r.solve(blocked,start,r.cell(xy(source)))
  if path and sum(math.dist(x,z) for x,z in zip(path,path[1:]))<7:
   add([xy(pad)]+path+[xy(source)],.2,layer);records.append({'pad':'.'.join(key),'method':'same-side','length_mm':sum(math.dist(x,z) for x,z in zip(path,path[1:]))});done=True;break
 if done:continue
 inner=LocalRouter(b,bounds,width=.5);middle=inner.blocked(p.In2_Cu,name);forbidden=set()
 for ly in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu):forbidden|=r.blocked(ly,name,.6,True)
 options=[]
 for q in sorted({(start[0]+dx,start[1]+dy) for dx in range(-80,81,2) for dy in range(-80,81,2)},key=lambda q:math.dist(q,start)):
  if not r.within(q) or q in forbidden or q in middle:continue
  if any(math.dist(r.world(q),xy(v))<.25+.15+p.ToMM(v.GetDrillValue())/2-1e-6 for v in b.GetTracks() if isinstance(v,p.PCB_VIA)):continue
  path=r.solve(blocked,start,q)
  if path and sum(math.dist(x,z) for x,z in zip(path,path[1:]))<4:options.append((q,[xy(pad)]+path))
  if len(options)==30:break
 found=None
 for q,path in options:
  for source in sorted(roots,key=lambda v:math.dist(xy(v),r.world(q))):
   bridge=inner.solve(middle,inner.cell(xy(source)),q)
   if bridge:found=q,path,bridge;break
  if found:break
 assert found,('No IO branch in bounded search',key)
 q,path,bridge=found;add(path,.2,layer);add(bridge,.5,p.In2_Cu);roots.append(via(r.world(q)));records.append({'pad':'.'.join(key),'method':'In2.Cu feed','via_xy_mm':r.world(q),'outer_length_mm':sum(math.dist(x,z) for x,z in zip(path,path[1:])),'inner_length_mm':sum(math.dist(x,z) for x,z in zip(bridge,bridge[1:]))});print(records[-1],flush=True)
p.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();reached={q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(pads['U4','55'])}
for key in [('R530','1'),('U25','22'),('C2007','1'),('Y2001','1'),('Y2001','4')]:assert pads[key].m_Uuid.AsString() in reached,('Missing IO continuity',key)
p.SaveBoard(str(a.output),b);a.report.write_text(json.dumps({'status':'GEOMETRY_AND_CONTINUITY_ONLY','board_sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'branches':records,'pmic_neck':{'width_mm':.127,'start_mm':[61.75,5.59],'end_mm':[61.75,4.65]},'outer_width_mm':.2,'inner_width_mm':.5,'via_land_drill_mm':[.6,.3],'remaining':['Source reservoir proximity and PMIC startup/load response','Voltage drop and thermal/current qualification','Physical tests'],'production_ready':False},indent=2)+'\n')
