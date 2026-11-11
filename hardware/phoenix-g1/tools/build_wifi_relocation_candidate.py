#!/usr/bin/env python3
"""Relocate Wi-Fi local copper as an isolated experiment, explicitly opening three boundary nets."""
import json,hashlib,math,os,heapq
from pathlib import Path
import pcbnew as p
from screen_wifi_relocation import GROUP,box,hit
R=Path(__file__).resolve().parents[1];P=R/'migration-rk3562/experiments/lpddr4-1gb';D=P/'wifi-relocation';SOURCE=P/'system/kicad/pcb/phoenix-lpddr4-placement.kicad_pcb'
def pt(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def trace_boxes(t):
 a,z=t.GetStart(),t.GetEnd();x,y=p.ToMM(a.x),p.ToMM(a.y);xx,yy=p.ToMM(z.x),p.ToMM(z.y);n=max(1,math.ceil(math.hypot(xx-x,yy-y)/.5));r=p.ToMM(t.GetWidth())/2
 return [(min(x+(xx-x)*i/n,x+(xx-x)*(i+1)/n)-r,min(y+(yy-y)*i/n,y+(yy-y)*(i+1)/n)-r,max(x+(xx-x)*i/n,x+(xx-x)*(i+1)/n)+r,max(y+(yy-y)*i/n,y+(yy-y)*(i+1)/n)+r) for i in range(n)]
def main():
 D.mkdir(exist_ok=True);b=p.LoadBoard(str(SOURCE));b.BuildConnectivity();conn=b.GetConnectivity();fs={f.GetReference():f for f in b.GetFootprints()};choice=json.loads((D/'placement-screen.json').read_text())['top_candidates'][int(os.environ.get('PHOENIX_WIFI_CHOICE','0'))];dx,dy=choice['delta_mm'];delta=pt(dx,dy);seen=set();clusters=[];removed=[];moved=[];opened=[];local_removed=[]
 for ref in sorted(GROUP):
  for pad in fs[ref].Pads():
   stack=[pad];tracks={};ends=set()
   while stack:
    a=stack.pop();uid=a.m_Uuid.AsString()
    if uid in seen:continue
    seen.add(uid)
    if isinstance(a,p.PAD):ends.add((a.GetParentFootprint().GetReference(),a.GetNumber()))
    else:tracks[uid]=a
    stack.extend(conn.GetConnectedTracks(a));stack.extend(conn.GetConnectedPads(a))
   if tracks:clusters.append((pad.GetNetname(),tracks,ends))
 # Preserve complete local copper geometry. Boundary clusters are explicitly removed, never silently stretched.
 for net,tracks,ends in clusters:
  outside=sorted(ref+'.'+pin for ref,pin in ends if ref not in GROUP)
  if outside:
   assert net in ('WIFI_VBAT','+3V3_IO','WIFI_LPO'),('Unexpected boundary',net,outside)
   opened.append({'net':net,'external_pads':outside,'all_pads':sorted(ref+'.'+pin for ref,pin in ends),'removed_items':len(tracks)})
   for t in tracks.values():removed.append(t);b.Remove(t)
  else:
   for t in tracks.values():
    if os.environ.get('PHOENIX_WIFI_REROUTE_LOCAL'):local_removed.append(t);b.Remove(t)
    else:t.Move(delta);moved.append(t)
 converter_feed_removed=[];converter_protected=set()
 if os.environ.get('PHOENIX_WIFI_REROUTE_LOCAL'):
  # Keep real shortest copper paths connecting every local output/sense endpoint.
  starts=next(q for q in fs['C2204'].Pads() if q.GetNumber()=='1');sid=starts.m_Uuid.AsString();items={sid:starts};cost={sid:0};prev={};queue=[(0,sid)]
  targets={next(q for q in fs[ref].Pads() if q.GetNumber()==pin).m_Uuid.AsString() for ref,pin in [('L2201','2'),('R2201','2'),('R2202','1'),('U26','14')]}
  while queue:
   distance,uid=heapq.heappop(queue)
   if distance>cost[uid]+1e-9:continue
   a=items[uid]
   for z in list(conn.GetConnectedTracks(a))+list(conn.GetConnectedPads(a)):
    if z.GetNetname()!='+3V58_WIFI':continue
    zid=z.m_Uuid.AsString();items[zid]=z;weight=.001 if isinstance(z,p.PAD) else .5 if isinstance(z,p.PCB_VIA) else p.ToMM(z.GetLength());new=distance+weight
    if new>=cost.get(zid,1e99):continue
    cost[zid]=new;prev[zid]=uid;heapq.heappush(queue,(new,zid))
  for uid in targets:
   assert uid in cost,'Local converter output endpoint disconnected in source'
   while uid!=sid:
    if not isinstance(items[uid],p.PAD):converter_protected.add(uid)
    uid=prev[uid]
  for t in list(b.GetTracks()):
   if t.GetNetname()=='+3V58_WIFI' and t.m_Uuid.AsString() not in converter_protected:converter_feed_removed.append(t);b.Remove(t)
  opened.append({'net':'+3V58_WIFI','external_pads':['C2204.1','FB2001.1'],'removed_items':len(converter_feed_removed),'note':'Local output and sense paths retained by copper graph; ferrite feed requires rerouting'})
 for ref in GROUP:fs[ref].Move(delta)
 coupon=p.LoadBoard(str(P/'cpu-simultaneous-coupon/cpu-simultaneous.kicad_pcb'));audit=json.loads((P/'cpu-simultaneous-coupon/audit.json').read_text());assert audit['board_sha256']==hashlib.sha256((P/'cpu-simultaneous-coupon/cpu-simultaneous.kicad_pcb').read_bytes()).hexdigest();nets={str(k):v for k,v in b.GetNetsByName().items()};cu=next(iter(coupon.GetFootprints()));offset=fs['U1'].GetPosition()-cu.GetPosition();added=0
 for old in coupon.GetTracks():
  t=old.Duplicate();t.SetNet(nets[old.GetNetname()]);t.Move(offset);b.Add(t);added+=1
 # Move only unrouted reverse-side parts obstructing the Wi-Fi group or newly placed through-vias.
 vias=[box(t) for t in b.GetTracks() if isinstance(t,p.PCB_VIA)]+[box(pad) for f in b.GetFootprints() for pad in f.Pads() if pad.GetAttribute()==p.PAD_ATTRIB_PTH];relocations=[]
 # Reserve a through-via corridor at the ferrite output before placing unrouted CPU bypasses.
 if os.environ.get('PHOENIX_WIFI_REROUTE_LOCAL'):vias.append((53.6,20.9,54.3,22.3))
 back_copper=[q for t in b.GetTracks() if not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.B_Cu for q in trace_boxes(t)]
 # Reserve output capacitor beside both buck endpoints before placing less constrained bypass parts.
 cap_reservation=None
 if os.environ.get('PHOENIX_WIFI_REROUTE_LOCAL'):
  f=fs['C2003'];anchors=[next(q for q in fs[ref].Pads() if q.GetNumber()==pin).GetPosition() for ref,pin in [('U25','23'),('L2001','2')]];anchors=[(p.ToMM(q.x),p.ToMM(q.y)) for q in anchors]
  fixed=[box(a) for ref,a in fs.items() if a!=f and a.GetLayer()==p.B_Cu and (ref in ('U25','L2001') or (ref not in GROUP and any(len(conn.GetConnectedTracks(q)) for q in a.Pads())))]+vias+back_copper
  candidates=[]
  for angle in (0,90,180,270):
   f.SetOrientationDegrees(angle)
   for xi in range(round((anchors[0][0]-7)*4),round((anchors[0][0]+7)*4)):
    for yi in range(round((anchors[0][1]-7)*4),min(156,round((anchors[0][1]+7)*4))):
     x,y=xi/4,yi/4;f.SetPosition(pt(x,y));bb=box(f)
     if bb[0]<1 or bb[1]<1 or bb[2]>89 or bb[3]>39 or any(hit(bb,z) for z in fixed):continue
     pad=next(q for q in f.Pads() if q.GetNumber()=='1');q=(p.ToMM(pad.GetPosition().x),p.ToMM(pad.GetPosition().y));dist=[math.dist(q,a) for a in anchors]
     if max(dist)>6:continue
     candidates.append((sum(dist),max(dist),x,y,angle))
  assert candidates,'Output capacitor needs coordinated placement beyond bounded search'
  _,_,x,y,angle=min(candidates);f.SetOrientationDegrees(angle);f.SetPosition(pt(x,y));cap_reservation={'ref':'C2003','xy_mm':[x,y],'angle_deg':angle,'reason':'Prioritized short output-capacitor paths; displaced unrouted bypasses may move'}
 io_reservation=None
 if os.environ.get('PHOENIX_WIFI_REROUTE_LOCAL'):
  f=fs['C2006'];anchor=next(q for q in fs['U25'].Pads() if q.GetNumber()=='22').GetPosition();anchor=(p.ToMM(anchor.x),p.ToMM(anchor.y))
  fixed=[box(a) for ref,a in fs.items() if a!=f and a.GetLayer()==p.B_Cu and (ref in ('U25','L2001','C2003') or (ref not in GROUP and any(len(conn.GetConnectedTracks(q)) for q in a.Pads())))]+vias+back_copper
  candidates=[]
  for angle in (0,90,180,270):
   f.SetOrientationDegrees(angle)
   for xi in range(round((anchor[0]-4)*4),round((anchor[0]+4)*4)):
    for yi in range(round((anchor[1]-4)*4),min(156,round((anchor[1]+4)*4))):
     x,y=xi/4,yi/4;f.SetPosition(pt(x,y));bb=box(f)
     if bb[0]<1 or bb[1]<1 or bb[2]>89 or bb[3]>39 or any(hit(bb,z) for z in fixed):continue
     pad=next(q for q in f.Pads() if q.GetNumber()=='1');distance=math.dist((p.ToMM(pad.GetPosition().x),p.ToMM(pad.GetPosition().y)),anchor)
     if distance<=3:candidates.append((distance,x,y,angle))
  assert candidates,'100n IO bypass needs coordinated placement'
  distance,x,y,angle=min(candidates);f.SetOrientationDegrees(angle);f.SetPosition(pt(x,y));io_reservation={'ref':'C2006','xy_mm':[x,y],'angle_deg':angle,'pad_distance_mm':distance}
 offsets=sorted([(i*.5,j*.5) for i in range(-60,61) for j in range(-60,61)],key=lambda z:math.hypot(*z))
 for ref,f in fs.items():
  if (ref=='C2006' and io_reservation) or (ref=='C2003' and cap_reservation) or (ref in GROUP and (ref=='U25' or not os.environ.get('PHOENIX_WIFI_REROUTE_LOCAL'))) or f.GetLayer()!=p.B_Cu:continue
  if not any(hit(box(f),box(fs[g])) for g in GROUP if g!=ref) and not any(hit(box(f),v) for v in vias) and not any(hit(box(f),q) for q in back_copper):continue
  if ref not in GROUP and any(len(conn.GetConnectedTracks(pad)) for pad in f.Pads()):continue
  old=[p.ToMM(f.GetPosition().x),p.ToMM(f.GetPosition().y)];obs=[box(a) for a in b.GetFootprints() if a!=f and a.GetLayer()==p.B_Cu]+vias+back_copper;found=None
  for xx,yy in offsets:
   x,y=old[0]+xx,old[1]+yy;f.SetPosition(pt(x,y));bb=box(f)
   if bb[0]<1 or bb[1]<1 or bb[2]>89 or bb[3]>39 or any(hit(bb,z) for z in obs):continue
   found=[x,y];break
  assert found,('No site for unrouted obstruction',ref)
  relocations.append({'ref':ref,'old_xy_mm':old,'xy_mm':found})
 b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(D/'candidate.kicad_pcb'),b)
 template=P/'cpu-board-integration';(D/'candidate.kicad_pro').write_text((template/'candidate.kicad_pro').read_text());(D/'candidate.kicad_dru').write_text((template/'candidate.kicad_dru').read_text());(D/'fp-lib-table').write_text((template/'fp-lib-table').read_text())
 report={'status':'RELOCATION_CANDIDATE_BOUNDARY_NETS_OPEN','source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256((D/'candidate.kicad_pcb').read_bytes()).hexdigest(),'module_xy_mm':choice['module_xy_mm'],'group':sorted(GROUP),'moved_local_copper_items':len(moved),'removed_boundary_copper_items':len(removed),'removed_local_copper_items':len(local_removed),'local_wifi_requires_rerouting':bool(local_removed),'removed_source_copper_uuids':sorted(t.m_Uuid.AsString() for t in removed+local_removed+converter_feed_removed),'removed_converter_feed_items':len(converter_feed_removed),'retained_converter_output_items':len(converter_protected),'opened_boundary_nets':opened,'output_capacitor_reservation':cap_reservation,'io_bypass_reservation':io_reservation,'unrouted_component_relocations':relocations,'CPU_escapes':audit['connected_escape_count'],'added_cpu_copper_items':added,'assembly_ready':False,'limits':['Boundary feeds and LPO require rerouting','RF path and crystal route incomplete','DDR remains incomplete','Bypass placement requires PDN review','Full-board DRC required']};(D/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['module_xy_mm','moved_local_copper_items','removed_boundary_copper_items','CPU_escapes']}))
if __name__=='__main__':main()
