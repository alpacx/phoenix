# Experimental local oscillator supply; not an upstream power trunk.
#!/usr/bin/env python3
"""AP6256 32.768 kHz signal routing only; oscillator supply and timing unqualified."""
import argparse,hashlib,json,math
from pathlib import Path
import pcbnew as p
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from local_pcb_router import LocalRouter
ap=argparse.ArgumentParser(description=__doc__)
for k in ('input','output','report'):ap.add_argument('--'+k,type=Path,required=True)
a=ap.parse_args();assert a.input.resolve()!=a.output.resolve()
b=p.LoadBoard(str(a.input));b.BuildConnectivity();pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()}

def point(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
def add(path,name,layer):
 total=0
 for x,z in zip(path,path[1:]):
  if math.dist(x,z)<1e-6:continue
  t=p.PCB_TRACK(b);t.SetStart(point(x));t.SetEnd(point(z));t.SetLayer(layer);t.SetWidth(p.FromMM(.2));t.SetNetCode(b.FindNet(name).GetNetCode());b.Add(t);total+=math.dist(x,z)
 return total
r=LocalRouter(b,(34,15,60,31),width=.2)
name='+3V3_IO';middle=r.blocked(p.In2_Cu,name);forbidden=set()
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
starts,goals=sites(pads['C2007','1'],p.F_Cu),sites(pads['C2006','1'],p.B_Cu)
print('Oscillator feed via candidates',len(starts),len(goals),flush=True)
selected=None
for qa,pa in starts:
 for qz,pz in goals:
  if math.dist(r.world(qa),r.world(qz))<.45:continue
  path=r.solve(middle,qa,qz)
  if path:selected=qa,pa,qz,pz,path;break
 if selected:break
assert selected,'No legal oscillator supply fanouts and inner path'
qa,pa,qz,pz,path=selected
lengths=[add(pa,name,p.F_Cu),add(path,name,p.In2_Cu),add(pz,name,p.B_Cu)]
for q in (qa,qz):
 v=p.PCB_VIA(b);v.SetPosition(point(r.world(q)));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.FindNet(name).GetNetCode());b.Add(v)
p.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();p.SaveBoard(str(a.output),b)
a.report.write_text(json.dumps({'status':'CANDIDATE LOCAL OSCILLATOR FEED; UPSTREAM PMIC STILL ABSENT','pcb_sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'lengths_mm':lengths,'vias_xy_mm':[r.world(qa),r.world(qz)],'width_mm':.2,'production_ready':False},indent=2)+'\n')
