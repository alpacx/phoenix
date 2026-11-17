"""Short PHY RXCLK strap; relocates only previously unrouted termination/strap."""
import pcbnew as p,math
from local_pcb_router import LocalRouter

def add_rxclk_strap_route(b):
 initial_ids={t.m_Uuid.AsString() for t in b.GetTracks()}
 b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()};pads={(f.GetReference(),q.GetNumber()):q for f in b.GetFootprints() for q in f.Pads()};assert not b.GetConnectivity().GetConnectedTracks(pads['R522','1'])
 f=fs['R512'];assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads())
 if f.GetLayer()!=p.B_Cu:f.Flip(f.GetPosition(),False)
 f.SetPosition(p.VECTOR2I(p.FromMM(63),p.FromMM(28.25)));f.SetOrientationDegrees(0)
 ids=[];held=[]
 for t in b.GetTracks():
  if t.GetNetname()=='GND' and not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu:
   a,z=t.GetStart(),t.GetEnd()
   if (tuple(a),tuple(z)) in {((56000000,27500000),(56000000,28250000)),((56010000,27500000),(56000000,27500000))}:ids.append(t.m_Uuid.AsString())
 for t in list(b.GetTracks()):
  if t.m_Uuid.AsString() in ids:
   assert t.GetNetname()=='GND' and t.GetWidth()==p.FromMM(.2);b.Remove(t);held.append(t)
 assert len(held)==2
 vec=lambda q:p.VECTOR2I(*(p.FromMM(c) for c in q));f=fs['R522'];f.Flip(f.GetPosition(),False)
 from local_pcb_router import LocalRouter
 r=LocalRouter(b,(60,26,67,33),width=.2,grid=.025);r.pads=[q for q in r.pads if q.GetParentFootprint().GetReference()!='R522'];blocked={q.GetNumber():r.blocked(p.B_Cu,q.GetNetname(),math.hypot(p.ToMM(q.GetSize().x),p.ToMM(q.GetSize().y))) for q in f.Pads()};boxes=[g.GetCourtyard(p.B_Cu).BBox() for g in b.GetFootprints() if g.GetReference()!='R522' and g.GetLayer()==p.B_Cu]
 choices=sorted([(x/4,y/4) for x in range(244,265) for y in range(108,129)],key=lambda q:math.dist(q,(63.25,29.5)));found=False
 for xy in choices:
  for angle in [180,0,90,270]:
   f.SetPosition(vec(xy));f.SetOrientationDegrees(angle)
   if any(f.GetCourtyard(p.B_Cu).BBox().Intersects(q) for q in boxes):continue
   if any(r.cell(r.xy(q)) in blocked[q.GetNumber()] for q in f.Pads()):continue
   rr=LocalRouter(b,(60,26,67,33),width=.2,grid=.025);path=rr.solve(rr.blocked(p.B_Cu,'PHY_RXCLK'),rr.cell(rr.xy(pads['R512','2'])),rr.cell(rr.xy(pads['R522','1'])))
   if not path:continue
   path=[rr.xy(pads['R512','2'])]+path+[rr.xy(pads['R522','1'])];length=sum(math.dist(a,z) for a,z in zip(path,path[1:]))
   if length>2.5:continue
   found=True;break
  if found:break
 assert found,'No short strap placement/path in bounded region'
 def route(net,points):
  for a,z in zip(points,points[1:]):
   if vec(a)==vec(z):continue
   t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(.2));t.SetLayer(p.B_Cu);t.SetNetCode(b.GetNetcodeFromNetname(net));b.Add(t)
 route('PHY_RXCLK',path)
 r=LocalRouter(b,(58,24,69,35),width=.2,grid=.025);start=r.xy(pads['R522','2']);tree=r.paths_from(r.blocked(p.B_Cu,'GND'),r.cell(start),6);forbidden=set()
 for lay in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:forbidden |= r.blocked(lay,'GND',.45,True)
 existing={r.cell(r.xy(v)):v for v in b.GetTracks() if isinstance(v,p.PCB_VIA) and v.GetNetname()=='GND'};sites=sorted((q for q in tree['distances'] if q not in forbidden or q in existing),key=lambda q:(tree['distances'][q],q));assert sites,'No ground escape'
 q=sites[0];gp=[start]+r.path_from_tree(tree,q);route('GND',gp)
 if q not in existing:
  v=p.PCB_VIA(b);v.SetPosition(vec(r.world(q)));v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(b.GetNetcodeFromNetname('GND'));b.Add(v)
 result={'replaced_copper':ids,'R512_position_mm':[63,28.25],'R522_position_mm':r.xy(f),'R522_orientation_deg':f.GetOrientationDegrees(),'layer':'B.Cu','strap_path_mm':path,'strap_length_mm':length,'ground_path_mm':gp,'ground_via_mm':r.world(q),'reused_ground_via':q in existing,'new_copper_uuids':[t.m_Uuid.AsString() for t in b.GetTracks() if t.m_Uuid.AsString() not in initial_ids]}
 return result,held
