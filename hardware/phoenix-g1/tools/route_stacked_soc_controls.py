#!/usr/bin/env python3
"""Experimental GPIO BGA escapes and low-speed bridge. Not SI qualification."""
import pcbnew as p,json,math,shutil,hashlib
from pathlib import Path
from local_pcb_router import LocalRouter
R=Path(__file__).resolve().parents[1];D=R/'migration-rk3562/experiments/stacked-expansion/pcb';b=p.LoadBoard(str(D/'connector-controls.kicad_pcb'));pads={(f.GetReference(),a.GetNumber()):a for f in b.GetFootprints() for a in f.Pads()};records=[]
def pt(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
for ball,jpin in [('K2','27'),('L3','28')]:
 pad=pads['U1',ball];name=pad.GetNetname();assert name==pads['J3',jpin].GetNetname()
 r=LocalRouter(b,(32,14,40,23),width=.0762,clearance=.0762);r.copper_clearance=.2;blocked=r.blocked(p.F_Cu,name);forbidden=set()
 for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu):forbidden|=r.blocked(layer,name,.6,True)
 inner=LocalRouter(b,(31,1,84,25),width=.2);middle=inner.blocked(p.In2_Cu,name);roots=[t for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()==name];found=None
 choices=[r.cell((ix/10,iy/10)) for ix in range(325,359) for iy in range(150,226)]
 for q in sorted(choices,key=lambda q:math.dist(r.world(q),r.xy(pad))):
  if q in forbidden:continue
  if any(math.dist(r.world(q),r.xy(v))<.25+.15+p.ToMM(v.GetDrillValue())/2-1e-6 for v in b.GetTracks() if isinstance(v,p.PCB_VIA)):continue
  path=r.solve(blocked,r.cell(r.xy(pad)),q)
  if not path or sum(math.dist(a,z) for a,z in zip(path,path[1:]))>8:continue
  for root in sorted(roots,key=lambda t:math.dist(r.xy(t),r.world(q))):
   bridge=inner.solve(middle,inner.cell(r.world(q)),inner.cell(r.xy(root)))
   if bridge:found=q,[r.xy(pad)]+path,bridge+[r.xy(root)];break
  if found:break
 assert found,('No BGA GPIO escape in bounded region',ball)
 q,path,bridge=found
 for layer,width,points in [(p.F_Cu,.0762,path),(p.In2_Cu,.2,bridge)]:
  for a,z in zip(points,points[1:]):
   if math.dist(a,z)<1e-6:continue
   t=p.PCB_TRACK(b);t.SetStart(pt(a));t.SetEnd(pt(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(pad.GetNetCode());b.Add(t)
 v=p.PCB_VIA(b);v.SetPosition(pt(r.world(q)));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(pad.GetNetCode());b.Add(v)
 b.BuildConnectivity();assert pads['J3',jpin].m_Uuid.AsString() in {i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(pad)}
 records.append({'ball':ball,'net':name,'J3_pin':jpin,'escape_via_mm':r.world(q),'escape_length_mm':sum(math.dist(a,z) for a,z in zip(path,path[1:]))});print(records[-1],flush=True)
p.ZONE_FILLER(b).Fill(b.Zones());dest=D/'soc-controls.kicad_pcb';p.SaveBoard(str(dest),b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(D/f'connector-controls.{ext}',dest.with_suffix('.'+ext))
with dest.with_suffix('.kicad_dru').open('a') as o:o.write('''\n(rule "Accessory GPIO CPU neck" (condition "A.NetName == 'EXP_GPIO0' || A.NetName == 'EXP_GPIO1'") (constraint track_width (min 0.0762mm)))\n''')
(D/'soc-controls.json').write_text(json.dumps({'status':'EXPERIMENTAL_ESCAPE_CONTINUITY_CHECKED_DRC_PENDING','routes':records,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'assembly_ready':False},indent=2)+'\n')
