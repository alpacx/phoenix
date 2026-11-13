#!/usr/bin/env python3
"""Accessory eFuse local ground escapes. Geometry only, not power or thermal signoff."""
import argparse, hashlib, json, math
from pathlib import Path
import pcbnew as p
from local_pcb_router import LocalRouter
ap=argparse.ArgumentParser(description=__doc__)
for arg in ('input','output','report'):ap.add_argument('--'+arg,type=Path,required=True)
ap.add_argument('--auto-bounds',action='store_true')
args=ap.parse_args();assert args.input.resolve()!=args.output.resolve()
b=p.LoadBoard(str(args.input));b.BuildConnectivity()
f=next(f for f in b.GetFootprints() if f.GetReference()=='J3')
assert f.GetLayer()==p.F_Cu
padrefs={a.m_Uuid.AsString():f.GetReference() for f in b.GetFootprints() for a in f.Pads()}
code=b.FindNet('GND').GetNetCode();records=[]
bounds=(60,.5,74,8)
if args.auto_bounds:
 x,y=p.ToMM(f.GetPosition().x),p.ToMM(f.GetPosition().y)
 bounds=(max(1,x-9),max(1,y-9),min(89,x+12),min(39,y+9))
def point(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
for pad in [a for f in b.GetFootprints() if f.GetReference()=='J3' for a in f.Pads() if a.GetNetname()=='GND']:
 r=LocalRouter(b,bounds,width=.2,clearance=.17);r.copper_clearance=.2
 start=r.cell(r.xy(pad));blocked=r.blocked(p.F_Cu,'GND');forbidden=set()
 for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu):
  forbidden |= r.blocked(layer,'GND',.6,True)
 existing={r.cell(r.xy(t)) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND'}
 choices={(start[0]+dx,start[1]+dy) for dx in range(-60,61,2) for dy in range(-60,61,2)} | existing
 best=None
 for q in sorted(choices,key=lambda q:math.dist(q,start)):
  if not r.within(q) or (q in forbidden and q not in existing):continue
  if q not in existing and any(math.dist(r.world(q),r.xy(t)) < .25+.15+p.ToMM(t.GetDrillValue())/2-1e-6 for t in b.GetTracks() if isinstance(t,p.PCB_VIA)):continue
  path=r.solve(blocked,start,q)
  if path and sum(math.dist(a,z) for a,z in zip(path,path[1:]))<=5:
   best=q,[r.xy(pad)]+path;break
 assert best,'No ground escape for '+padrefs[pad.m_Uuid.AsString()]+'.'+pad.GetNumber()
 q,path=best;length=0
 for a,z in zip(path,path[1:]):
  if math.dist(a,z)<1e-6:continue
  t=p.PCB_TRACK(b);t.SetStart(point(a));t.SetEnd(point(z));t.SetLayer(p.F_Cu);t.SetWidth(p.FromMM(.2));t.SetNetCode(code);b.Add(t);length+=math.dist(a,z)
 if q not in existing:
  v=p.PCB_VIA(b);v.SetPosition(point(r.world(q)));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(code);b.Add(v)
 records.append({'ref':padrefs[pad.m_Uuid.AsString()],'pin':pad.GetNumber(),'via_xy_mm':r.world(q),'reused_via':q in existing,'path_length_mm':round(length,4)})
 print(records[-1],flush=True)
p.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity()
p.SaveBoard(str(args.output),b)
args.report.write_text(json.dumps({'status':'CANDIDATE GROUND ESCAPES; DRC REQUIRED','pcb_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'escapes':records,'trace_width_mm':.2,'new_via_land_drill_mm':[.6,.3],'limitations':['RF return inductance and power-ground impedance not qualified.','Signal routing, internal regulator and power sequencing remain incomplete.'],'production_ready':False},indent=2)+'\n')
