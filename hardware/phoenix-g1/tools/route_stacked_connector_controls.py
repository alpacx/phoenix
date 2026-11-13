#!/usr/bin/env python3
"""Route J3 enable/fault to local eFuse controls. SoC escapes remain separate."""
import pcbnew as p,math,json,shutil,hashlib
from pathlib import Path
from local_pcb_router import LocalRouter
R=Path(__file__).resolve().parents[1];D=R/'migration-rk3562/experiments/stacked-expansion/pcb';b=p.LoadBoard(str(D/'connector-ground.kicad_pcb'));pads={(f.GetReference(),a.GetNumber()):a for f in b.GetFootprints() for a in f.Pads()};records=[]
def pt(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
for pin,ref in [('27','R8103'),('28','R8102')]:
 start,end=pads['J3',pin],pads[ref,'1'];name=start.GetNetname();assert end.GetNetname()==name
 r=LocalRouter(b,(60,.5,85,12),width=.2,clearance=.17);r.copper_clearance=.2;inner=LocalRouter(b,(60,.5,85,12),width=.2);middle=inner.blocked(p.In2_Cu,name);forbidden=set()
 for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu):forbidden|=r.blocked(layer,name,.6,True)
 def options(pad,layer):
  r.clearance=.17 if layer==p.F_Cu else .2
  center=r.cell(r.xy(pad));blocked=r.blocked(layer,name);out=[]
  for q in sorted({(center[0]+dx,center[1]+dy) for dx in range(-80,81,2) for dy in range(-80,81,2)},key=lambda q:math.dist(q,center)):
   if not r.within(q) or q in forbidden or q in middle:continue
   if any(math.dist(r.world(q),r.xy(v))<.25+.15+p.ToMM(v.GetDrillValue())/2-1e-6 for v in b.GetTracks() if isinstance(v,p.PCB_VIA)):continue
   path=r.solve(blocked,center,q)
   if path and sum(math.dist(a,z) for a,z in zip(path,path[1:]))<8:out.append((q,[r.xy(pad)]+path))
   if len(out)==16:break
  return out
 first=options(start,p.F_Cu);second=options(end,p.B_Cu);found=None
 for q,path in first:
  for z,tail in second:
   bridge=inner.solve(middle,q,z)
   if bridge:found=q,path,z,tail,bridge;break
  if found:break
 assert found,('No path',name,len(first),len(second))
 q,path,z,tail,bridge=found
 for layer,points in [(p.F_Cu,path),(p.B_Cu,tail),(p.In2_Cu,bridge)]:
  for a,c in zip(points,points[1:]):
   if math.dist(a,c)<1e-6:continue
   t=p.PCB_TRACK(b);t.SetStart(pt(a));t.SetEnd(pt(c));t.SetLayer(layer);t.SetWidth(p.FromMM(.2));t.SetNetCode(start.GetNetCode());b.Add(t)
 for cell in [q,z]:
  v=p.PCB_VIA(b);v.SetPosition(pt(r.world(cell)));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(start.GetNetCode());b.Add(v)
 b.BuildConnectivity();assert end.m_Uuid.AsString() in {i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(start)}
 records.append({'from':'J3.'+pin,'to':ref+'.1','net':name,'vias_mm':[r.world(q),r.world(z)],'length_mm':sum(math.dist(a,c) for points in [path,tail,bridge] for a,c in zip(points,points[1:]))});print(records[-1],flush=True)
p.ZONE_FILLER(b).Fill(b.Zones());out=D/'connector-controls.kicad_pcb';p.SaveBoard(str(out),b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(D/f'connector-ground.{ext}',out.with_suffix('.'+ext))
(D/'connector-controls.json').write_text(json.dumps({'status':'CONTINUITY_CHECKED_DRC_PENDING','routes':records,'SoC_connected':False,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'assembly_ready':False},indent=2)+'\n')
