#!/usr/bin/env python3
"""Bounded draft routing of USB CC and VBUS sensing, with explicit DRC required.
Use KiCad Python. Includes explicitly scoped supply candidates and ground planes;
not complete power delivery or high-speed routing.
"""
from pathlib import Path
import pcbnew as p,json,math,heapq,shutil,sys
R=Path(__file__).resolve().parents[1]/'migration-rk3562';OUT=R/'kicad/pcb';OUT.mkdir(exist_ok=True)
aon='--aon' in sys.argv
sense_power='--power-sense' in sys.argv
returns='--returns' in sys.argv
auxiliary='--auxiliary' in sys.argv
controls='--controls' in sys.argv or auxiliary or returns or sense_power or aon
resume=('--continue' in sys.argv) or (controls and '--fresh' not in sys.argv)
b=p.LoadBoard(str(OUT/'phoenix-g1.kicad_pcb' if resume else R/'kicad/floorplan/phoenix-g1-floorplan.kicad_pcb'))
step=.05;width=.2;clearance=.2;extent=(.5,.5,30.,39.5);layers=[p.F_Cu,p.B_Cu]
def mm(v):return p.ToMM(v)
def point(xy):return p.VECTOR2I(p.FromMM(xy[0]),p.FromMM(xy[1]))
def pad_xy(ref,number):
 a=next(a for a in pads if a.GetParentFootprint().GetReference()==ref and a.GetNumber()==number)
 return (mm(a.GetPosition().x),mm(a.GetPosition().y))
def cell(xy):return tuple(round(v/step) for v in xy)
def world(c):return (c[0]*step,c[1]*step)
pads=[a for f in b.GetFootprints() for a in f.Pads()]
zones=list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()]
def obstacle(layer,name,diameter=None,for_via=False):
 if diameter is None:diameter=width
 blocked=set();margin=clearance+diameter/2-1e-6
 def rectangle(x0,y0,x1,y1):
  for x in range(math.ceil(max(x0,extent[0])/step),math.floor(min(x1,extent[2])/step)+1):
   for y in range(math.ceil(max(y0,extent[1])/step),math.floor(min(y1,extent[3])/step)+1):blocked.add((x,y))
 # Copper edges must remain 0.25 mm inside the 90 x 40 mm board,
 # including the via land radius (checking the via center alone is insufficient).
 border=.25+diameter/2
 rectangle(0,0,border-1e-6,40);rectangle(0,0,90,border-1e-6)
 rectangle(90-border+1e-6,0,90,40);rectangle(0,40-border+1e-6,90,40)
 for a in pads:
  if not a.IsOnLayer(layer) or (a.GetNetname()==name and not for_via):continue
  q=a.GetBoundingBox(layer);x0,y0,x1,y1=[mm(v) for v in (q.GetX(),q.GetY(),q.GetRight(),q.GetBottom())]
  rectangle(x0-margin,y0-margin,x1+margin,y1+margin)
 for z in zones:
  if not(z.GetIsRuleArea() and z.IsOnLayer(layer) and (z.GetDoNotAllowVias() if for_via else z.GetDoNotAllowTracks())):continue
  q=z.GetBoundingBox();a=diameter/2+.01;x0,y0,x1,y1=[mm(v) for v in (q.GetX(),q.GetY(),q.GetRight(),q.GetBottom())];rectangle(x0-a,y0-a,x1+a,y1+a)
 for t in b.GetTracks():
  if not t.IsOnLayer(layer):continue
  if t.GetNetname()==name:
   if for_via and isinstance(t,p.PCB_VIA):
    vx,vy=mm(t.GetPosition().x),mm(t.GetPosition().y)
    # Same-net copper may overlap, drilled holes still need 0.25 mm edge clearance.
    rr=.25+(.3+mm(t.GetDrillValue()))/2
    for x in range(math.floor((vx-rr)/step),math.ceil((vx+rr)/step)+1):
     for y in range(math.floor((vy-rr)/step),math.ceil((vy+rr)/step)+1):
      if math.dist(world((x,y)),(vx,vy))<rr-1e-6:blocked.add((x,y))
   continue
  a=(mm(t.GetStart().x),mm(t.GetStart().y));z=(mm(t.GetEnd().x),mm(t.GetEnd().y));rad=clearance+(diameter+mm(t.GetWidth(layer) if isinstance(t,p.PCB_VIA) else t.GetWidth()))/2
  dx,dy=z[0]-a[0],z[1]-a[1];den=dx*dx+dy*dy
  for x in range(math.floor((min(a[0],z[0])-rad)/step),math.ceil((max(a[0],z[0])+rad)/step)+1):
   for y in range(math.floor((min(a[1],z[1])-rad)/step),math.ceil((max(a[1],z[1])+rad)/step)+1):
    wx,wy=world((x,y));u=max(0,min(1,((wx-a[0])*dx+(wy-a[1])*dy)/den)) if den else 0
    if math.hypot(wx-a[0]-u*dx,wy-a[1]-u*dy)<rad-1e-6:blocked.add((x,y))
 return blocked
def solve(blocked,start,goal):
 if start in blocked or goal in blocked:return None
 q=[(math.dist(start,goal),0,start)];dist={start:0};prev={}
 while q:
  _,cost,c=heapq.heappop(q)
  if cost!=dist[c]:continue
  if c==goal:
   path=[goal]
   while path[-1]!=start:path.append(prev[path[-1]])
   path=path[::-1];compact=[path[0]]
   for i in range(1,len(path)-1):
    if (path[i][0]-path[i-1][0],path[i][1]-path[i-1][1])!=(path[i+1][0]-path[i][0],path[i+1][1]-path[i][1]):compact.append(path[i])
   if len(path)>1:compact.append(path[-1])
   return [world(c) for c in compact]
  for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
   n=(c[0]+dx,c[1]+dy);xy=world(n)
   if n in blocked or not(extent[0]<=xy[0]<=extent[2] and extent[1]<=xy[1]<=extent[3]):continue
   if dx and dy and ((c[0]+dx,c[1]) in blocked or (c[0],c[1]+dy) in blocked):continue
   bend=.15 if c in prev and (c[0]-prev[c][0],c[1]-prev[c][1])!=(dx,dy) else 0;d=cost+math.hypot(dx,dy)+bend
   if d<dist.get(n,float('inf')):dist[n]=d;prev[n]=c;heapq.heappush(q,(d+math.dist(n,goal),d,n))
 return None
def add_tracks(xy,layer,net):
 length=0;count=0
 for a,z in zip(xy,xy[1:]):
  if math.dist(a,z)<.00001:continue
  t=p.PCB_TRACK(b);t.SetStart(point(a));t.SetEnd(point(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNetCode(net);b.Add(t);length+=math.dist(a,z);count+=1
 return length,count
# Reserve short same-layer bypass paths before signal fanout.
if not resume:
 for ar,ap,zr,zp in [('C1101','1','U11','1'),('C1102','1','U11','5'),('C1201','1','U15','4'),('U15','3','U15','4'),('C1203','1','U15','5'),('C1901','1','U24','11'),('U24','11','U24','12'),('U24','12','U24','13'),('U24','11','U24','10'),('U24','10','U24','9'),('C1902','1','U24','5'),('U24','5','U24','4'),('U24','5','U24','6'),('U24','6','U24','7'),('U24','7','U24','8')]:
  a=next(x for x in pads if x.GetParentFootprint().GetReference()==ar and x.GetNumber()==ap)
  z=next(x for x in pads if x.GetParentFootprint().GetReference()==zr and x.GetNumber()==zp)
  assert a.GetNetCode()==z.GetNetCode() and a.IsOnLayer(p.F_Cu) and z.IsOnLayer(p.F_Cu)
  width=.5 if ar in ['C1201','C1901','C1902'] else .25
  add_tracks([(mm(a.GetPosition().x),mm(a.GetPosition().y)),(mm(z.GetPosition().x),mm(z.GetPosition().y))],p.F_Cu,a.GetNetCode())
  width=.2
 for ref,target,pin in [('C1103','U12','6'),('C1104','U13','5'),('C1105','U14','5'),('C1106','U16','5'),('C1107','U19','5'),('C606','U6','8')]:
  a=next(x for x in pads if x.GetParentFootprint().GetReference()==ref and x.GetNumber()=='1')
  z=next(x for x in pads if x.GetParentFootprint().GetReference()==target and x.GetNumber()==pin)
  width=.2 if target=='U6' else .25
  xy=[(mm(q.GetPosition().x),mm(q.GetPosition().y)) for q in [a,z]]
  path=solve(obstacle(p.F_Cu,'+3V3_AON'),*map(cell,xy))
  assert path and sum(math.dist(a,z) for a,z in zip(path,path[1:]))<5,(ref,'No short local bypass path')
  add_tracks([xy[0]]+path+[xy[1]],p.F_Cu,a.GetNetCode())
 width=.2
thermal=[]
if not resume:
 # TI package drawing examples: RVC0020A p41 and RNH0030A p46.
 # Via-in-exposed-pad fill/plug and paste process remain assembly holds.
 for ref,pin,xs,ys in [('U24','21',[-1,0,1],[-.5,.5]),('U6','31',[-1.2,0,1.2],[-.35,.35])]:
  pad=next(a for a in pads if a.GetParentFootprint().GetReference()==ref and a.GetNumber()==pin)
  cx,cy=mm(pad.GetPosition().x),mm(pad.GetPosition().y)
  for dx in xs:
   for dy in ys:
    via=p.PCB_VIA(b);via.SetPosition(point((cx+dx,cy+dy)));via.SetWidth(p.FromMM(.45));via.SetDrill(p.FromMM(.2));via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNetCode(pad.GetNetCode());b.Add(via)
    thermal.append({'ref':ref,'xy_mm':[cx+dx,cy+dy],'land_drill_mm':[.45,.2]})
 (R/'review/usb-thermal-vias.json').write_text(json.dumps({'vias':thermal,'status':'CANDIDATE; FILL/PLUG AND STENCIL NOT QUALIFIED','sources':['reference/tps25940-official.pdf p41','reference/hd3ss3220.pdf p46','https://jlcpcb.com/capabilities/pcb-capabilities/']},indent=2)+'\n')
if not resume:
 # Candidate VBUS backbone. Width is explicit; no current/thermal signoff.
 name='VBUS_RAW';net=next(a.GetNetCode() for a in pads if a.GetNetname()==name)
 width=.3
 for path in [[(6.24,18.75),(6.95,18.75),(7.2,18.5),(9.0,18.5),(9.2,17.9)],[(6.24,21.25),(6.95,21.25),(7.2,21.5),(9.0,21.5),(9.2,22.1)]]:
  add_tracks(path,p.F_Cu,net)
 width=.5;add_tracks([pad_xy('C1901','1'),(11.05,5.45),(11.75,5.45)],p.F_Cu,net)
 for x,y in [(9.0,18.5),(9.2,17.9),(9.0,21.5),(9.2,22.1),(11.05,5.45),(11.75,5.45)]:
  via=p.PCB_VIA(b);via.SetPosition(point((x,y)));via.SetWidth(p.FromMM(.6));via.SetDrill(p.FromMM(.3));via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNetCode(net);b.Add(via)
 width=1.5;power_paths=[]
 for start,goal in [((9.1,18.2),(3.5,18.5)),((3.5,18.5),(3.5,5.45)),((3.5,5.45),(11.4,5.45)),((9.1,21.8),(3.5,21.5)),((3.5,21.5),(3.5,18.5))]:
  route=solve(obstacle(p.In2_Cu,name),cell(start),cell(goal))
  assert route,'No 1.5 mm VBUS backbone route'
  length,count=add_tracks(route,p.In2_Cu,net);power_paths.append({'length_mm':length,'width_mm':width,'layer':'In2.Cu'})
 width=.2
 (R/'review/usb-vbus-backbone.json').write_text(json.dumps({'status':'CANDIDATE; DRC AND CURRENT/TEMPERATURE QUALIFICATION REQUIRED','paths':power_paths,'via_land_drill_mm':[.6,.3],'via_count':6,'inner_copper_nominal_um_candidates':[17.5,35],'source':'https://jlcpcb.com/help/article/jlcpcb-copper-weight','production_ready':False},indent=2)+'\n')
if not resume:
 name='VBUS_PROTECTED';net=next(a.GetNetCode() for a in pads if a.GetNetname()==name)
 width=.5
 add_tracks([pad_xy('C1902','1'),(9.8,10.7),(10.5,10.7)],p.F_Cu,net)
 add_tracks([pad_xy('C1201','1'),(5.0,32.95),(5.7,32.95)],p.F_Cu,net)
 for x,y in [(9.8,10.7),(10.5,10.7),(5.0,32.95),(5.7,32.95)]:
  via=p.PCB_VIA(b);via.SetPosition(point((x,y)));via.SetWidth(p.FromMM(.6));via.SetDrill(p.FromMM(.3));via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNetCode(net);b.Add(via)
 width=1.5;protected_paths=[]
 for start,goal in [((10.15,10.7),(12.5,11.0)),((12.5,11.0),(12.5,36.0)),((12.5,36.0),(5.35,36.0)),((5.35,36.0),(5.35,32.95))]:
  route=solve(obstacle(p.In2_Cu,name),cell(start),cell(goal))
  assert route,'No 1.5 mm protected supply route'
  length,count=add_tracks(route,p.In2_Cu,net);protected_paths.append({'start_mm':start,'end_mm':goal,'length_mm':length,'width_mm':width,'layer':'In2.Cu'})
 width=.2
 (R/'review/usb-protected-backbone.json').write_text(json.dumps({'status':'CANDIDATE; DRC AND CURRENT/TEMPERATURE QUALIFICATION REQUIRED','paths':protected_paths,'via_land_drill_mm':[.6,.3],'via_count':4,'production_ready':False},indent=2)+'\n')
if returns:
 refs={'J1','U6','U7','U8','R1102','R1103','U9','U11','U12','U13','U14','U15','U19','U24','C1103','C1104','C1105','C1106','C1107','C606','U16','C605','C1101','C1102','C1201','C1202','C1203','C1901','C1902','C1903','R1201','R1902','R1904','R1905'}
 results=[];failed=[];thermal=json.loads((R/'review/usb-thermal-vias.json').read_text())['vias']
 ground=[a for a in pads if a.GetNetname()=='GND' and a.GetParentFootprint().GetReference() in refs]
 for pad in sorted(ground,key=lambda a:(a.GetParentFootprint().GetReference(),a.GetNumber())):
  layer=p.F_Cu if pad.IsOnLayer(p.F_Cu) else p.B_Cu
  xy=(mm(pad.GetPosition().x),mm(pad.GetPosition().y));start=cell(xy);name='GND';net=pad.GetNetCode()
  blocked=obstacle(layer,name);vb=obstacle(p.F_Cu,name,.45,True)|obstacle(p.B_Cu,name,.45,True)|obstacle(p.In3_Cu,name,.45,True)|obstacle(p.In2_Cu,name,.45,True)
  options=[]
  for dx in range(-60,61,2):
   for dy in range(-60,61,2):
    c=(start[0]+dx,start[1]+dy);v=world(c)
    if c not in vb and c not in blocked and extent[0]<=v[0]<=extent[2] and extent[1]<=v[1]<=extent[3]:options.append(c)
  existing={cell((mm(t.GetPosition().x),mm(t.GetPosition().y))) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND'}
  options=sorted(set(options)|existing,key=lambda c:math.dist(c,start))
  for c in options[:250]:
   path=solve(blocked,start,c)
   if not path or sum(math.dist(a,z) for a,z in zip(path,path[1:]))>4:continue
   length,count=add_tracks([xy]+path,layer,net)
   if c not in existing:
    via=p.PCB_VIA(b);via.SetPosition(point(world(c)));via.SetWidth(p.FromMM(.45));via.SetDrill(p.FromMM(.2));via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNetCode(net);b.Add(via)
   results.append({'pin':pad.GetParentFootprint().GetReference()+'.'+pad.GetNumber(),'via_xy_mm':world(c),'length_mm':round(length,4)});break
  else:failed.append(pad.GetParentFootprint().GetReference()+'.'+pad.GetNumber())
 net=ground[0].GetNetCode()
 for layer in [p.In1_Cu,p.In4_Cu]:
  zone=p.ZONE(b);zone.SetLayer(layer);zone.SetNetCode(net);zone.SetLocalClearance(p.FromMM(.2));zone.SetMinThickness(p.FromMM(.15));zone.SetPadConnection(p.ZONE_CONNECTION_FULL)
  outline=zone.Outline();outline.NewOutline()
  for x,y in [(.25,.25),(89.75,.25),(89.75,39.75),(.25,39.75)]:outline.Append(p.FromMM(x),p.FromMM(y))
  b.Add(zone)
 p.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity()
 # Remove only unused preliminary signal vias; preserve all ground/thermal vias.
 reservations=json.loads((R/'review/usb-sense-routing.json').read_text())['initial_fanout']
 reserved={(a['net'],cell(a['via_xy_mm'])) for a in reservations if a['net']!='GND'}
 removed=[];connectivity=b.GetConnectivity()
 for via in list(b.GetTracks()):
  if not isinstance(via,p.PCB_VIA) or (via.GetNetname(),cell((mm(via.GetPosition().x),mm(via.GetPosition().y)))) not in reserved:continue
  connected_layers={t.GetLayer() for t in connectivity.GetConnectedTracks(via) if t.GetClass()=='PCB_TRACK'}
  connected_layers.update(layer for a in connectivity.GetConnectedPads(via) for layer in [p.F_Cu,p.B_Cu] if a.IsOnLayer(layer))
  if len(connected_layers)==1:
   matching=[a for a in reservations if a['net']==via.GetNetname() and cell(a['via_xy_mm'])==cell((mm(via.GetPosition().x),mm(via.GetPosition().y)))]
   unused_ids={uid for a in matching for uid in a.get('segment_uuids',[])}
   for stub in list(b.GetTracks()):
    if stub.m_Uuid.AsString() in unused_ids:b.Remove(stub)
   removed.append({'net':via.GetNetname(),'xy_mm':[mm(via.GetPosition().x),mm(via.GetPosition().y)]});b.Remove(via)
 if removed:p.ZONE_FILLER(b).Fill(b.Zones())
 p.SaveBoard(str(OUT/'phoenix-g1.kicad_pcb'),b)

 report={'status':'CANDIDATE USB GROUND RETURNS; DRC REQUIRED','routed':results,'removed_unused_preliminary_vias':removed,'thermal_vias_candidate':thermal,'failed_pins':failed,'candidate_ground_layers':['In1.Cu','In4.Cu'],'limitations':['Stackup and impedance not qualified. Thermal vias follow TI hole-location examples with candidate 0.45mm lands; filling/plugging, stencil and assembly price are unqualified.','USB source ground continuity must pass the separate filled-copper audit; power distribution and current/thermal qualification remain incomplete.','0.20 mm local return stubs are not a main-current or thermal design. Non-thermal return vias also use 0.45/0.20 mm land/drill.'],'production_ready':False}
 (R/'review/usb-ground-routing.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));sys.exit(0)
# Reserve short escapes before long traces can fence in fine-pitch control pins.
# These are ordinary through vias outside pads, not via-in-pad fabrication.
fanout=[]
if not resume:
 for ref,number in [('R1901','1'),('R1903','1'),('TP2','1'),('U12','3'),('R603','1'),('R602','1'),('R604','1'),('R1101','1'),('R1202','2'),('U9','4'),('U9','5'),('U11','2'),('C1902','2'),('C605','1'),('C605','2'),('C1203','2'),('U14','3'),('U15','2'),('U15','1'),('U15','7'),('U15','6'),('U24','14'),('U24','15'),('U24','17'),('U24','18')]+[('U6',n) for n in ['30','29','26','25','1','2','5']]+[('R1902','2'),('R1905','2')]+[('C1103','2'),('C1104','2'),('C1105','2'),('C1106','2'),('C1107','2'),('C606','2'),('U16','3')]:
  pad=next(a for a in pads if a.GetParentFootprint().GetReference()==ref and a.GetNumber()==number)
  name=pad.GetNetname();xy=(mm(pad.GetPosition().x),mm(pad.GetPosition().y));start=cell(xy)
  escape_layer=p.F_Cu if pad.IsOnLayer(p.F_Cu) else p.B_Cu
  fan_land,fan_drill=(.45,.2) if name in ['USB_CC1','USB_CC2','GND'] or (ref=='U6' and number in ['30','5']) else (.6,.3)
  front=obstacle(escape_layer,name);vb=obstacle(p.F_Cu,name,fan_land,True)|obstacle(p.B_Cu,name,fan_land,True)|obstacle(p.In3_Cu,name,fan_land,True)|obstacle(p.In2_Cu,name,fan_land,True)
  options=[]
  span=80 if ref=='U9' else 60
  for dx in range(-span,span+1,2):
   for dy in range(-span,span+1,2):
    c=(start[0]+dx,start[1]+dy);v=world(c)
    if c not in vb and c not in front and extent[0]<=v[0]<=extent[2] and extent[1]<=v[1]<=extent[3]:options.append(c)
  preferred={('U24','17'):(2.7,7.15),('U24','18'):(3.2,8.85),('U6','1'):(14.8,22.2),('U6','2'):(15.6,21.9),('U9','4'):(9.3,17.0),('U9','5'):(13.8,18.6),('U15','7'):(8.2,30.8),('U15','6'):(8.3,31.8)}.get((ref,number),xy)
  options.sort(key=lambda c:math.dist(world(c),preferred))
  for c in options:
   path=solve(front,start,c)
   if path and sum(math.dist(a,z) for a,z in zip(path,path[1:]))<=4:
    prior_ids={t.m_Uuid.AsString() for t in b.GetTracks()}
    length,count=add_tracks([xy]+path,escape_layer,pad.GetNetCode())
    segment_ids=[t.m_Uuid.AsString() for t in b.GetTracks() if t.m_Uuid.AsString() not in prior_ids]
    via=p.PCB_VIA(b);via.SetPosition(point(world(c)));via.SetWidth(p.FromMM(fan_land));via.SetDrill(p.FromMM(fan_drill));via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNetCode(pad.GetNetCode());b.Add(via)
    fanout.append({'pin':ref+'.'+number,'net':name,'via_xy_mm':world(c),'length_mm':length,'segment_uuids':segment_ids});break
  else:
   p.SaveBoard('/tmp/phoenix-routing-failure.kicad_pcb',b)
   raise RuntimeError('No safe preliminary escape for '+ref+'.'+number)
results=[];failures=[];tasks=[]
for name in ['CC_VBUS_SENSE','CC_VBUS_SERIES_2','CC_VBUS_SERIES_1']:
 ends=[a for a in pads if a.GetNetname()==name];assert len(ends)==2;tasks.append((name,ends))
for name in ['USB_CC2','USB_CC1']:
 ends={a.GetParentFootprint().GetReference():a for a in pads if a.GetNetname()==name};assert set(ends)=={'J1','U9','U6'}
 tasks.extend([(name,[ends['J1'],ends['U9']]),(name,[ends['U9'],ends['U6']])])
if controls:
 tasks=[]
 names=['+3V3_AON'] if aon else ['VBUS_UVLO','VBUS_OVP','VBUS_GUARD_ILIM','VBUS_GUARD_DVDT','USB_DVDT','USB_ILIM','USB_POWER_FAULT_N'] if auxiliary else ['AON_READY','CC_OUT2_N','CC_OUT1_N','USB_CURRENT_OK','USB_MAIN_ENABLE']
 for name in names:
  ends=sorted([a for a in pads if a.GetNetname()==name],key=lambda a:(a.GetParentFootprint().GetReference(),a.GetNumber()))
  assert len(ends)>=2 and all(a.IsOnLayer(p.F_Cu) or a.IsOnLayer(p.B_Cu) for a in ends),name
  joined=[ends.pop(0)]
  while ends:
   a,z=min(((a,z) for a in joined for z in ends),key=lambda az:math.hypot(mm(az[0].GetPosition().x-az[1].GetPosition().x),mm(az[0].GetPosition().y-az[1].GetPosition().y)))
   tasks.append((name,[a,z]));joined.append(z);ends.remove(z)
if not controls:
 tasks.insert(0,('USB_CC_ENABLE_N',sorted([a for a in pads if a.GetNetname()=='USB_CC_ENABLE_N'],key=lambda a:a.GetParentFootprint().GetReference())))
if sense_power:
 # Only divider inputs and the test pad: these are not load-current paths.
 target=next(a for a in pads if a.GetParentFootprint().GetReference()=='C1901' and a.GetNumber()=='1')
 tasks=[('VBUS_RAW',[next(a for a in pads if a.GetParentFootprint().GetReference()==ref and a.GetNumber()=='1'),target]) for ref in ['R1901','R1903','TP2']]
 # Auxiliary regulator input and sensing feeds; the main load uses the wide backbone.
 for ar,ap,zr,zp in [('U11','3','U11','1'),('C1101','1','C1201','1'),('U6','30','C1902','1'),('R601','1','C1902','1'),('C605','1','C1902','1')]:
  pair=[next(a for a in pads if a.GetParentFootprint().GetReference()==ref and a.GetNumber()==pin) for ref,pin in [(ar,ap),(zr,zp)]]
  assert all(a.GetNetname()=='VBUS_PROTECTED' for a in pair)
  tasks.append(('VBUS_PROTECTED',pair))
for name,ends in tasks:
 via_land,via_drill=(.45,.2) if name in ['USB_CC1','USB_CC2'] else (.6,.3)
 if sense_power or aon:
  b.BuildConnectivity()
  if any(i.m_Uuid==ends[1].m_Uuid for i in b.GetConnectivity().GetConnectedItems(ends[0])):
   results.append({'net':name,'already_connected':True,'length_mm':0,'segments':0,'vias_xy_mm':[],'endpoints':[a.GetParentFootprint().GetReference()+'.'+a.GetNumber() for a in ends]});continue
 try:
  coords=[(mm(a.GetPosition().x),mm(a.GetPosition().y)) for a in ends];start,goal=map(cell,coords);net=ends[0].GetNetCode()
  on_front=[a.IsOnLayer(p.F_Cu) for a in ends]
  front=obstacle(p.F_Cu,name);path=solve(front,start,goal) if all(on_front) else None;vias=[];sections=[]
  if any(a.GetParentFootprint().GetReference() in ['U6','U15','U24'] for a in ends):path=None
  # Move CC2 off the front connector escape corridor before routing CC1.
  if name=='USB_CC2' and any(a.GetParentFootprint().GetReference()=='J1' for a in ends):path=None
  if path and sum(math.dist(a,z) for a,z in zip(path,path[1:]))>3*math.dist(*coords)+10:path=None
  if path:sections=[(p.F_Cu,[coords[0]]+path+[coords[1]])]
  else:
   inner=auxiliary or sense_power or aon or name in ['CC_OUT1_N','CC_OUT2_N']
   transit=p.In3_Cu if inner else p.B_Cu
   back=obstacle(transit,name);vb=obstacle(p.F_Cu,name,via_land,True)|obstacle(p.B_Cu,name,via_land,True)|obstacle(transit,name,via_land,True)|obstacle(p.In2_Cu,name,via_land,True)
   candidates=[]
   for endpoint_index,endpoint in enumerate([start,goal]):
    if not on_front[endpoint_index] and not inner:
     assert endpoint not in back,(name,"Back-layer endpoint blocked")
     candidates.append([(endpoint,[world(endpoint)])]);continue
    entry=p.F_Cu if on_front[endpoint_index] else p.B_Cu
    entry_blocked=obstacle(entry,name)
    options=[]
    via_grid=2 if name in ['USB_CC1','USB_CC2'] else 5
    for dx in range(-60,61,via_grid):
     for dy in range(-60,61,via_grid):
      c=(endpoint[0]+dx,endpoint[1]+dy);xy=world(c)
      if c not in vb and c not in entry_blocked and c not in back and extent[0]<=xy[0]<=extent[2] and extent[1]<=xy[1]<=extent[3]:options.append(c)
    options.extend(cell((mm(t.GetPosition().x),mm(t.GetPosition().y))) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetCode()==net)
    saved_fanout=fanout if fanout else json.loads((R/'review/usb-sense-routing.json').read_text())['initial_fanout']
    endpoint_label=ends[endpoint_index].GetParentFootprint().GetReference()+'.'+ends[endpoint_index].GetNumber()
    preferred_sites={cell(a['via_xy_mm']) for a in saved_fanout if a['pin']==endpoint_label and endpoint_label in ['U9.4','U9.5']}
    options=sorted(set(options),key=lambda c:(c not in preferred_sites,math.dist(c,endpoint)));reachable=[]
    for c in options[:160]:
     path=solve(entry_blocked,endpoint,c)
     if path:reachable.append((c,path))
     if len(reachable)==5:break
    assert reachable,(name,world(endpoint),'endpoint blocked='+str(endpoint in front),'No safe via site');candidates.append(reachable)
   for a,pa in candidates[0]:
    for z,pz in candidates[1]:
     middle=solve(back,a,z)
     if middle:
      vias=[world(c) for i,c in enumerate([a,z]) if on_front[i] or inner]
      sections=[]
      if on_front[0] or inner:sections.append((p.F_Cu if on_front[0] else p.B_Cu,[coords[0]]+pa))
      else:middle=[coords[0]]+middle
      if on_front[1] or inner:sections.append((p.F_Cu if on_front[1] else p.B_Cu,list(reversed(pz))+[coords[1]]))
      else:middle=middle+[coords[1]]
      sections.append((transit,middle));break
    if sections:break
   assert sections,(name,'No back-layer route')
   for v in vias:
    if any(isinstance(t,p.PCB_VIA) and t.GetNetCode()==net and math.dist((mm(t.GetPosition().x),mm(t.GetPosition().y)),v)<.001 for t in b.GetTracks()):continue
    via=p.PCB_VIA(b);via.SetPosition(point(v));via.SetWidth(p.FromMM(via_land));via.SetDrill(p.FromMM(via_drill));via.SetViaType(p.VIATYPE_THROUGH);via.SetLayerPair(p.F_Cu,p.B_Cu);via.SetNetCode(net);b.Add(via)
  length=count=0
  for layer,xy in sections:
   l,c=add_tracks(xy,layer,net);length+=l;count+=c
  results.append({'net':name,'length_mm':round(length,4),'segments':count,'vias_xy_mm':vias,'via_land_drill_mm':[via_land,via_drill],'endpoints':[a.GetParentFootprint().GetReference()+'.'+a.GetNumber() for a in ends]})
 except AssertionError as exc:
  if '--debug-failure' in sys.argv:p.SaveBoard('/tmp/phoenix-routing-failure.kicad_pcb',b)
  if "--allow-partial" not in sys.argv:raise
  failures.append({"net":name,"endpoints":[a.GetParentFootprint().GetReference()+"."+a.GetNumber() for a in ends],"reason":str(exc)})
for drawing in b.GetDrawings():
 if isinstance(drawing,p.PCB_TEXT) and 'UNROUTED STUDY' in drawing.GetText():drawing.SetText(drawing.GetText().replace('UNROUTED STUDY','PARTIAL ROUTING DRAFT'))
b.BuildConnectivity();b.GetConnectivity().RecalculateRatsnest();b.GetTitleBlock().SetTitle('Phoenix RK3562 - PARTIALLY ROUTED DRAFT - NOT FOR FABRICATION');p.SaveBoard(str(OUT/'phoenix-g1.kicad_pcb'),b)
for src,dst in ([] if resume else [('fp-lib-table','fp-lib-table'),('phoenix-g1-floorplan.kicad_pro','phoenix-g1.kicad_pro')]):shutil.copy2(R/'kicad/floorplan'/src,OUT/dst)
project=OUT/'phoenix-g1.kicad_pro';meta=json.loads(project.read_text());meta['meta']['filename']=project.name;meta['board']['design_settings']['rules'].update({'min_through_hole_diameter':.2,'min_via_diameter':.45});project.write_text(json.dumps(meta,indent=2)+'\n')
report={'status':'PARTIAL USB CONTROL ROUTING; RUN DRC BEFORE ACCEPTING','nets':results,'initial_fanout':fanout,'failed_branches':failures,'track_width_mm':width,'search_clearance_mm':clearance,'via_land_drill_mm':[.6,.3],'cc_via_land_drill_mm':[.45,.2],'track_and_via_items':len(list(b.GetTracks())),'unconnected_ratsnest_edges':b.GetConnectivity().GetUnconnectedCount(False),'limitations':['Only the reported USB controls and explicit supply branches are routed. Full board routing, USB data, remaining power rails and qualification remain unresolved.','Candidate SoC footprint, stackup, ESD return paths, PI, decoupling and mechanics unqualified.','CC detours need optimization; DRC alone does not establish electrical performance.'],'production_ready':False}
(R/('review/usb-aon-routing.json' if aon else 'review/usb-power-sense-routing.json' if sense_power else 'review/usb-auxiliary-routing.json' if auxiliary else 'review/usb-control-routing.json' if controls else 'review/usb-sense-routing.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
