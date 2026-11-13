#!/usr/bin/env python3
"""Draft accessory input feed. Geometry only; current/thermal budget remains unqualified."""
import pcbnew as p,math,json,shutil,hashlib
from pathlib import Path
from local_pcb_router import LocalRouter
R=Path(__file__).resolve().parents[1];D=R/'migration-rk3562/experiments/stacked-expansion/pcb';b=p.LoadBoard(str(D/'fault-supply.kicad_pcb'));pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};pad=pads['C8101','1'];name='+5V_MAIN';assert pad.GetNetname()==name;r=LocalRouter(b,(48,2,84,36),width=.3);start=r.cell(r.xy(pad));outer=r.blocked(p.B_Cu,name);power=LocalRouter(b,(48,2,84,36),width=1.0);inner=power.blocked(p.In3_Cu,name);forbidden=set()
for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu):forbidden|=r.blocked(layer,name,.6,True)
roots=[v for v in b.GetTracks() if isinstance(v,p.PCB_VIA) and v.GetNetname()==name and r.within(r.cell(r.xy(v)))];assert roots
found=None
for q in sorted({(start[0]+dx,start[1]+dy) for dx in range(-50,51,2) for dy in range(-50,51,2)},key=lambda q:math.dist(q,start)):
 if not r.within(q) or q in forbidden or q in inner:continue
 if any(math.dist(r.world(q),r.xy(t))<.25+.15+p.ToMM(t.GetDrillValue())/2-1e-6 for t in b.GetTracks() if isinstance(t,p.PCB_VIA)):continue
 path=r.solve(outer,start,q)
 if not path:continue
 for root in sorted(roots,key=lambda v:math.dist(r.xy(v),r.world(q))):
  bridge=power.solve(inner,q,r.cell(r.xy(root)))
  if bridge:found=q,[r.xy(pad)]+path,bridge+[r.xy(root)],root;break
 if found:break
assert found,'No bounded path'
q,path,bridge,root=found
def pt(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
for layer,route in [(p.B_Cu,path),(p.In3_Cu,bridge)]:
 for x,y in zip(route,route[1:]):
  if math.dist(x,y)<1e-6:continue
  t=p.PCB_TRACK(b);t.SetStart(pt(x));t.SetEnd(pt(y));t.SetLayer(layer);t.SetWidth(p.FromMM(.3 if layer==p.B_Cu else 1.0));t.SetNetCode(pad.GetNetCode());b.Add(t)
v=p.PCB_VIA(b);v.SetPosition(pt(r.world(q)));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(pad.GetNetCode());b.Add(v)
p.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();assert pads['U26','13'].m_Uuid.AsString() in {i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(pad)}
dest=D/'input-feed.kicad_pcb';p.SaveBoard(str(dest),b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(D/f'candidate.{ext}',dest.with_suffix('.'+ext))
(D/'input-feed.json').write_text(json.dumps({'status':'CONTINUITY_CHECKED_DRC_PENDING','from':'C8101.1','to':'U26.13','outer_neck_width_mm':.3,'inner_width_mm':1.0,'current_rating_qualified':False,'USB_budget_allocated':False,'via_mm':r.world(q),'length_mm':sum(math.dist(x,y) for route in [path,bridge] for x,y in zip(route,route[1:])),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'assembly_ready':False},indent=2)+'\n')
