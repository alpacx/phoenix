#!/usr/bin/env python3
"""Local AP6256 internal-buck copper; no switching-node vias or electrical signoff."""
import argparse,hashlib,json,math
from pathlib import Path
import pcbnew as p
from local_pcb_router import LocalRouter
ap=argparse.ArgumentParser(description=__doc__)
for k in ('input','output','report'):ap.add_argument('--'+k,type=Path,required=True)
ap.add_argument('--auto-bounds',action='store_true')
ap.add_argument('--allow-output-vias',action='store_true',help='Allow a qualified-later inner-layer output connection; never the switch node')
a=ap.parse_args();assert a.input.resolve()!=a.output.resolve()
b=p.LoadBoard(str(a.input));b.BuildConnectivity()
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
for ref in ('L2001','C2003'):
 assert all(q.IsOnLayer(p.B_Cu) for (r,_),q in pads.items() if r==ref)
 assert not any(b.GetConnectivity().GetConnectedTracks(q) for (r,_),q in pads.items() if r==ref)
bounds=(34,22,44,33)
if a.auto_bounds:
 anchors=[pads[k].GetPosition() for k in [('U25','21'),('U25','23'),('L2001','1'),('L2001','2'),('C2003','1'),('C2003','2')]]
 xs=[p.ToMM(q.x) for q in anchors];ys=[p.ToMM(q.y) for q in anchors]
 bounds=(max(1,min(xs)-2.5),max(1,min(ys)-2.5),min(89,max(xs)+2.5),min(39,max(ys)+2.5))
def point(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
def add(path,name,width,layer=p.B_Cu):
 total=0
 for x,z in zip(path,path[1:]):
  if math.dist(x,z)<1e-6:continue
  t=p.PCB_TRACK(b);t.SetStart(point(x));t.SetEnd(point(z));t.SetLayer(layer);t.SetWidth(p.FromMM(width));t.SetNetCode(b.FindNet(name).GetNetCode());b.Add(t);total+=math.dist(x,z)
 return total
records=[]
for start,end,width in [(('U25','21'),('L2001','1'),.5),(('L2001','2'),('C2003','1'),.6),(('U25','23'),('C2003','1'),.5)]:
 x,z=pads[start],pads[end];name=x.GetNetname();assert name==z.GetNetname()
 r=LocalRouter(b,bounds,width=width)
 path=r.solve(r.blocked(p.B_Cu,name),r.cell(r.xy(x)),r.cell(r.xy(z)))
 if not path and a.allow_output_vias and start==('U25','23'):
  assert name=='WIFI_BUCK_OUT'
  forbidden=set()
  for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu):forbidden|=r.blocked(layer,name,.6,True)
  middle=r.blocked(p.In3_Cu,name);outer=r.blocked(p.B_Cu,name)
  def sites(pad):
   cell=r.cell(r.xy(pad));choices=[]
   for q in sorted({(cell[0]+dx,cell[1]+dy) for dx in range(-60,61,2) for dy in range(-60,61,2)},key=lambda q:math.dist(q,cell)):
    if not r.within(q) or q in forbidden or q in middle:continue
    line=r.solve(outer,cell,q)
    if line and sum(math.dist(c,d) for c,d in zip(line,line[1:]))<3:choices.append((q,[r.xy(pad)]+line))
    if len(choices)==20:break
   return choices
  sources,targets=sites(x),sites(z);bridge=None
  for qx,px in sources:
   for qz,pz in targets:
    if math.dist(r.world(qx),r.world(qz))<.85:continue
    mid=r.solve(middle,qx,qz)
    if mid and sum(math.dist(c,d) for line in (px,mid,pz) for c,d in zip(line,line[1:]))<9:bridge=(qx,px,qz,pz,mid);break
   if bridge:break
  assert bridge,'No short output bridge; placement revision required'
  qx,px,qz,pz,mid=bridge;length=add(px,name,width)+add(mid,name,width,p.In3_Cu)+add(pz,name,width)
  for q in (qx,qz):
   via=p.PCB_VIA(b);via.SetPosition(point(r.world(q)));via.SetWidth(p.FromMM(.6));via.SetDrill(p.FromMM(.3));via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNetCode(b.FindNet(name).GetNetCode());b.Add(via)
  records.append({'from':'.'.join(start),'to':'.'.join(end),'net':name,'width_mm':width,'length_mm':round(length,4),'layer':'B.Cu / In3.Cu','output_vias_mm':[r.world(qx),r.world(qz)],'via_land_drill_mm':[.6,.3],'requires_PDN_validation':True});print(records[-1],flush=True);continue
 assert path,'No local buck route '+str((start,end))
 path=[r.xy(x)]+path+[r.xy(z)]
 length=sum(math.dist(x,z) for x,z in zip(path,path[1:]));assert length<7,'Buck route requires placement revision'
 add(path,name,width);records.append({'from':'.'.join(start),'to':'.'.join(end),'net':name,'width_mm':width,'length_mm':round(length,4),'layer':'B.Cu'})
 print(records[-1],flush=True)
r=LocalRouter(b,bounds,width=.5);pad=pads['C2003','2'];start=r.cell(r.xy(pad));forbidden=set();blocked=r.blocked(p.B_Cu,'GND')
for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu):forbidden |= r.blocked(layer,'GND',.6,True)
existing={r.cell(r.xy(t)) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND'}
choices={(start[0]+dx,start[1]+dy) for dx in range(-60,61,2) for dy in range(-60,61,2)}|existing
selected=None
for q in sorted(choices,key=lambda q:math.dist(q,start)):
 if not r.within(q) or (q in forbidden and q not in existing):continue
 if q not in existing and any(math.dist(r.world(q),r.xy(t))<.25+.15+p.ToMM(t.GetDrillValue())/2-1e-6 for t in b.GetTracks() if isinstance(t,p.PCB_VIA)):continue
 path=r.solve(blocked,start,q)
 if path and sum(math.dist(x,z) for x,z in zip(path,path[1:]))<3:
  selected=q,[r.xy(pad)]+path;break
assert selected,'No local buck-cap ground return'
q,path=selected;length=add(path,'GND',.5)
if q not in existing:
 v=p.PCB_VIA(b);v.SetPosition(point(r.world(q)));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.FindNet('GND').GetNetCode());b.Add(v)
p.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();p.SaveBoard(str(a.output),b)
a.report.write_text(json.dumps({'status':'CANDIDATE LOCAL BUCK COPPER; DRC AND INDEPENDENT AUDIT REQUIRED','pcb_sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'branches':records,'ground_escape':{'via_xy_mm':r.world(q),'reused':q in existing,'width_mm':.5,'length_mm':round(length,4)},'limitations':['No electrical simulation or hardware test.','Inductor saturation, effective capacitance, ripple, stability and return impedance remain unqualified.','Displaced SoC decoupling requires later local placement review.'],'production_ready':False},indent=2)+'\n')
