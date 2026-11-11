# EXPERIMENT ONLY: not integrated; local continuity does not qualify electrical layout.
#!/usr/bin/env python3
"""Local AP6256 internal-buck copper; no switching-node vias or electrical signoff."""
import argparse,hashlib,json,math
from pathlib import Path
import pcbnew as p
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3] / 'tools'))
from local_pcb_router import LocalRouter
ap=argparse.ArgumentParser(description=__doc__)
for k in ('input','output','report'):ap.add_argument('--'+k,type=Path,required=True)
a=ap.parse_args();assert a.input.resolve()!=a.output.resolve()
b=p.LoadBoard(str(a.input));b.BuildConnectivity()
pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}
for ref in ('L2001','C2003'):
 assert all(q.IsOnLayer(p.B_Cu) for (r,_),q in pads.items() if r==ref)
 assert not any(b.GetConnectivity().GetConnectedTracks(q) for (r,_),q in pads.items() if r==ref)
def point(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
def add(path,name,width,layer=p.B_Cu):
 total=0
 for x,z in zip(path,path[1:]):
  if math.dist(x,z)<1e-6:continue
  t=p.PCB_TRACK(b);t.SetStart(point(x));t.SetEnd(point(z));t.SetLayer(layer);t.SetWidth(p.FromMM(width));t.SetNetCode(b.FindNet(name).GetNetCode());b.Add(t);total+=math.dist(x,z)
 return total
records=[]
for start,end,width in [(('U25','21'),('L2001','1'),.5),(('U25','23'),('C2003','1'),.5),(('L2001','2'),('C2003','1'),.6)]:
 x,z=pads[start],pads[end];name=x.GetNetname();assert name==z.GetNetname()
 r=LocalRouter(b,(34,22,44,33),width=width)
 path=r.solve(r.blocked(p.B_Cu,name),r.cell(r.xy(x)),r.cell(r.xy(z)))
 if path is None and start==('L2001','2'):
  middle=r.blocked(p.In3_Cu,name);forbidden=set()
  for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu):forbidden |= r.blocked(layer,name,.6,True)
  def sites(pad):
   startcell=r.cell(r.xy(pad));result=[];blocked=r.blocked(p.B_Cu,name)
   for q in sorted({(startcell[0]+dx,startcell[1]+dy) for dx in range(-80,81,2) for dy in range(-80,81,2)},key=lambda q:math.dist(q,startcell)):
    if not r.within(q) or q in forbidden or q in middle:continue
    if any(math.dist(r.world(q),r.xy(t))<.25+.15+p.ToMM(t.GetDrillValue())/2-1e-6 for t in b.GetTracks() if isinstance(t,p.PCB_VIA)):continue
    pa=r.solve(blocked,startcell,q)
    if pa and sum(math.dist(u,v) for u,v in zip(pa,pa[1:]))<6:
     result.append((q,[r.xy(pad)]+pa))
     if len(result)>=20:break
   return result
  starts,goals=sites(x),sites(z);print('OUT via candidates',len(starts),len(goals),flush=True);selected=None
  for qa,pa in starts:
   for qz,pz in goals:
    if math.dist(r.world(qa),r.world(qz))<.55:continue
    pm=r.solve(middle,qa,qz)
    if pm:selected=qa,pa,qz,pz,pm;break
   if selected:break
  assert selected,'No legal OUT inner bridge'
  qa,pa,qz,pz,pm=selected
  lengths=[add(pa,name,width),add(pm,name,width,p.In3_Cu),add(pz,name,width)]
  for q in (qa,qz):
   v=p.PCB_VIA(b);v.SetPosition(point(r.world(q)));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.FindNet(name).GetNetCode());b.Add(v)
  records.append({'from':'.'.join(start),'to':'.'.join(end),'net':name,'lengths_mm':lengths,'via_xy_mm':[r.world(qa),r.world(qz)],'experimental':True})
  continue
 assert path,'No local buck route '+str((start,end))
 path=[r.xy(x)]+path+[r.xy(z)]
 length=sum(math.dist(x,z) for x,z in zip(path,path[1:]));assert length<7,'Buck route requires placement revision'
 add(path,name,width);records.append({'from':'.'.join(start),'to':'.'.join(end),'net':name,'width_mm':width,'length_mm':round(length,4),'layer':'B.Cu'})
 print(records[-1],flush=True)
r=LocalRouter(b,(34,22,44,33),width=.5);pad=pads['C2003','2'];start=r.cell(r.xy(pad));forbidden=set();blocked=r.blocked(p.B_Cu,'GND')
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
