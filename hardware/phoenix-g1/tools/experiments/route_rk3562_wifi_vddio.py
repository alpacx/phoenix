#!/usr/bin/env python3
"""EXPERIMENTAL, NOT INTEGRATED. Local AP6256 VDDIO bypass copper; upstream PMIC feed is outside this stage."""
import argparse,hashlib,json,math
from pathlib import Path
import pcbnew as p
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_pcb_router import LocalRouter
ap=argparse.ArgumentParser(description=__doc__)
for k in ('input','output','report'):ap.add_argument('--'+k,type=Path,required=True)
ap.add_argument('--auto-bounds',action='store_true')
a=ap.parse_args();assert a.input.resolve()!=a.output.resolve()
b=p.LoadBoard(str(a.input));b.BuildConnectivity()
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
for ref in ('C2004','C2005','C2006'):
 assert all(q.IsOnLayer(p.B_Cu) for (r,_),q in pads.items() if r==ref and q.GetNetname()!='GND')
 assert not any(b.GetConnectivity().GetConnectedTracks(q) for (r,_),q in pads.items() if r==ref and q.GetNetname()!='GND')
bounds=(32,19,44,30)
if a.auto_bounds:
 anchors=[pads[k].GetPosition() for k in [('U25','22')]+[(ref,pin) for ref in ('C2004','C2005','C2006') for pin in ('1','2')]]
 xs=[p.ToMM(q.x) for q in anchors];ys=[p.ToMM(q.y) for q in anchors]
 bounds=(max(1,min(xs)-2.5),max(1,min(ys)-2.5),min(89,max(xs)+2.5),min(39,max(ys)+2.5))
def point(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
def add(path,name,width,layer=p.B_Cu):
 total=0
 for x,z in zip(path,path[1:]):
  if math.dist(x,z)<1e-6:continue
  t=p.PCB_TRACK(b);t.SetStart(point(x));t.SetEnd(point(z));t.SetLayer(layer);t.SetWidth(p.FromMM(width));t.SetNetCode(b.FindNet(name).GetNetCode());b.Add(t);total+=math.dist(x,z)
 return total
grounds=[]
for ref in ('C2006','C2005','C2004'):
 r=LocalRouter(b,bounds,width=.3);pad=pads[ref,'2'];start=r.cell(r.xy(pad));forbidden=set();blocked=r.blocked(p.B_Cu,'GND')
 for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu):forbidden |= r.blocked(layer,'GND',.45,True)
 existing={r.cell(r.xy(t)) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND'}
 choices={(start[0]+dx,start[1]+dy) for dx in range(-60,61,2) for dy in range(-60,61,2)}|existing
 selected=None
 for q in sorted(choices,key=lambda q:math.dist(q,start)):
  if not r.within(q) or (q in forbidden and q not in existing):continue
  if q not in existing and any(math.dist(r.world(q),r.xy(t))<.25+.15+p.ToMM(t.GetDrillValue())/2-1e-6 for t in b.GetTracks() if isinstance(t,p.PCB_VIA)):continue
  path=r.solve(blocked,start,q)
  if path and sum(math.dist(x,z) for x,z in zip(path,path[1:]))<3:
   selected=q,[r.xy(pad)]+path;break
 assert selected,'No local VDDIO-cap ground return '+ref
 q,path=selected;length=add(path,'GND',.3)
 if q not in existing:
  v=p.PCB_VIA(b);v.SetPosition(point(r.world(q)));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.FindNet('GND').GetNetCode());b.Add(v)
 grounds.append({'ref':ref,'via_xy_mm':r.world(q),'reused':q in existing,'width_mm':.3,'length_mm':round(length,4)})
 print(grounds[-1],flush=True)

records=[]
for start,end,width in [(('U25','22'),('C2006','1'),.3),(('C2006','1'),('C2005','1'),.4),(('C2005','1'),('C2004','1'),.4)]:
 x,z=pads[start],pads[end];name=x.GetNetname();assert name==z.GetNetname()
 r=LocalRouter(b,bounds,width=width)
 path=r.solve(r.blocked(p.B_Cu,name),r.cell(r.xy(x)),r.cell(r.xy(z)))
 assert path,'No local VDDIO route '+str((start,end))
 path=[r.xy(x)]+path+[r.xy(z)]
 length=sum(math.dist(x,z) for x,z in zip(path,path[1:]));assert length<7,'VDDIO route requires placement revision'
 add(path,name,width);records.append({'from':'.'.join(start),'to':'.'.join(end),'net':name,'width_mm':width,'length_mm':round(length,4),'layer':'B.Cu'})
 print(records[-1],flush=True)
p.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();p.SaveBoard(str(a.output),b)
a.report.write_text(json.dumps({'status':'CANDIDATE LOCAL VDDIO BYPASS; UPSTREAM FEED STILL REQUIRED','pcb_sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'branches':records,'ground_escapes':grounds,'limitations':['No electrical simulation or hardware test.','Effective capacitance and return impedance remain unqualified; upstream PMIC output is not routed by this stage.','Displaced SoC decoupling requires later local placement review.'],'production_ready':False},indent=2)+'\n')
