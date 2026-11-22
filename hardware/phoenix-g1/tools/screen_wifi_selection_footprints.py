"""Screen adjacent footprints for mutually exclusive RF links on the module face, before DNP selection."""
from pathlib import Path
from collections import Counter
import hashlib,math,json,os,sys,heapq
from functools import lru_cache
bent='--bent-feed' in sys.argv
tee='--center-feed' in sys.argv or bent
branch='--shared-feed' in sys.argv or tee
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';data=json.loads((root/'layout-usb-enable-trunk.json').read_text());src=root/data['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==data['sha256']
b=p.LoadBoard(str(src));module=b.FindFootprintByReference('U25');q=module.FindPadByNumber('2');start=tuple(q.GetPosition());res=b.FindFootprintByReference('R2001');side=module.GetLayer();v=lambda pos:p.VECTOR2I(*pos)
if res.GetLayer()!=side:res.Flip(res.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
original_net=q.GetNetCode();obs=[o for o in list(b.GetTracks())+[pad for f in b.GetFootprints() if f.GetReference()!='R2001' for pad in f.Pads()] if inflated_box(o,4500000).Contains(v(start))]
sh=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in obs if o.IsOnLayer(side)]
drills=[o.GetEffectiveHoleShape() for o in obs if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
courts=[(f.GetReference(),f.GetCourtyard(side)) for f in b.GetFootprints() if f.GetReference()!='R2001' and f.GetLayer()==side and inflated_box(f,5000000).Contains(v(start))]
keep=[z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
counts=Counter();near=Counter();candidates=[];land_poses=[];track=p.PCB_TRACK(b);track.SetLayer(side);track.SetNetCode(original_net)
for ang in range(0,360,45):
 res.SetOrientationDegrees(ang)
 for ix in (range(22,83) if branch else range(-8,31)):
  for iy in (range(-38,47) if branch else range(-26,27)):
   grid=50000 if branch else 100000
   pos=(start[0]+ix*grid,start[1]+iy*grid)
   if math.dist(start,pos)>(4300000 if branch else 3000000):continue
   res.SetPosition(v(pos));cy=res.GetCourtyard(side);cl=[name for name,k in courts if k.OutlineCount() and cy.Collide(k,100000)]
   if cl:
    if len(cl)==1:near[cl[0]]+=1
    continue
   counts['courtyard_clear']+=1;good=True
   for pad in res.Pads():
    shape=pad.GetEffectiveShape(side);bb=inflated_box(pad,400000)
    if any(n!=pad.GetNetCode() and bb.Intersects(ob) and shape.Collide(obj,202000) for n,obj,ob in sh) or any(shape.Collide(h,252000) for h in drills):good=False;break
   if not good:continue
   counts['lands_clear']+=1;end=tuple(res.FindPadByNumber('1').GetPosition());src_edge=(start[0]+280000,start[1]);land_poses.append(dict(pos_nm=pos,angle=ang,common_nm=end));track.SetStart(v(src_edge));track.SetEnd(v(end));track.SetWidth(335000);shape=track.GetEffectiveShape(side);bb=inflated_box(track,400000)
   if any(n!=original_net and bb.Intersects(ob) and shape.Collide(obj,202000) for n,obj,ob in sh) or any(shape.Collide(h,252000) for h in drills) or any(shape.Collide(k,0) for k in keep):continue
   candidates.append(dict(pos_nm=pos,angle=ang,common_nm=end,feed_mm=math.dist(src_edge,end)/1e6))
ground=[z.GetFilledPolysList(p.In4_Cu) for z in b.Zones() if z.GetNetname()=='GND' and z.IsOnLayer(p.In4_Cu) and z.HasFilledPolysForLayer(p.In4_Cu)]
src_edge=(start[0]+280000,start[1])
@lru_cache(None)
def edge(u,z):
 track.SetStart(v(u));track.SetEnd(v(z));tsh=track.GetEffectiveShape(side);box=inflated_box(track,410000)
 if any(n!=original_net and box.Intersects(ob) and tsh.Collide(s,202000) for n,s,ob in sh) or any(tsh.Collide(h,252000) for h in drills) or any(tsh.Collide(k,0) for k in keep):return False
 delta=math.dist(u,z);nn=max(1,math.ceil(delta/25000))
 return all(any(polygon.Contains(v(tuple(round(a+(j-a)*i/nn) for a,j in zip(u,z)))) for polygon in ground) for i in range(nn+1))
dist={src_edge:0};prev={};queue=[(0,src_edge)];step=50000
while queue and bent:
 c,u=heapq.heappop(queue)
 if c!=dist[u]:continue
 for ix,iy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
  z=(u[0]+ix*step,u[1]+iy*step);nc=c+math.hypot(ix,iy)*step
  if nc>=dist.get(z,1e99) or nc>6500000 or abs(z[1]-start[1])>3200000 or not edge(u,z):continue
  prev[z]=u;dist[z]=nc;heapq.heappush(queue,(nc,z))
pairs=[];nearest=None;best_ref=None;pc=Counter();candidates.sort(key=lambda a:a['feed_mm'])
for i,a in enumerate(candidates):
 res.SetOrientationDegrees(a['angle']);res.SetPosition(v(a['pos_nm']));a_cy=p.SHAPE_POLY_SET(res.GetCourtyard(side));a_box=a_cy.BBox()
 for z in (land_poses if branch else candidates[i+1:]):
  sep=math.dist(a['common_nm'],z['common_nm'])
  if sep>(2300000 if branch else 1150000):continue
  res.SetOrientationDegrees(z['angle']);res.SetPosition(v(z['pos_nm']));box=res.GetCourtyard(side).BBox()
  if a_cy.Collide(res.GetCourtyard(side),100000):continue
  pc['separated_courts']+=1
  if branch:
   track.SetStart(v(a['common_nm']));track.SetEnd(v(z['common_nm']));st=track.GetEffectiveShape(side);en=inflated_box(track,410000)
   if any(n!=original_net and en.Intersects(ob) and st.Collide(obj,202000) for n,obj,ob in sh) or any(st.Collide(h,252000) for h in drills) or any(st.Collide(k,0) for k in keep):continue
   unselected=res.FindPadByNumber('2').GetEffectiveShape(side)
   if st.Collide(unselected,202000):continue
   res.SetOrientationDegrees(a['angle']);res.SetPosition(v(a['pos_nm']))
   if st.Collide(res.FindPadByNumber('2').GetEffectiveShape(side),202000):continue
  entry=dict(first=a,second=z,common_pad_spacing_mm=sep/1e6)
  if tee:
   mid=tuple(round((i+j)/2) for i,j in zip(a['common_nm'],z['common_nm']))
   if bent:
    close=sorted((dist[u]+math.dist(u,mid),u) for ix in range(-1,2) for iy in range(-1,2) for u in [(src_edge[0]+(round((mid[0]-src_edge[0])/step)+ix)*step,src_edge[1]+(round((mid[1]-src_edge[1])/step)+iy)*step)] if u in dist and edge(u,mid))
    if not close:continue
    path=[close[0][1]]
    while path[-1]!=src_edge:path.append(prev[path[-1]])
    path.reverse();path.append(mid)
   else:path=[src_edge,mid]
   track.SetStart(v(path[-2]));track.SetEnd(v(mid));srf=track.GetEffectiveShape(side);en=inflated_box(track,410000)
   if any(n!=original_net and en.Intersects(ob) and srf.Collide(obj,202000) for n,obj,ob in sh) or any(srf.Collide(h,252000) for h in drills) or any(srf.Collide(k,0) for k in keep):continue
   bad=False
   for part in (a,z):
    res.SetOrientationDegrees(part['angle']);res.SetPosition(v(part['pos_nm']))
    for u,last in zip(path,path[1:]):
     track.SetStart(v(u));track.SetEnd(v(last))
     if track.GetEffectiveShape(side).Collide(res.FindPadByNumber('2').GetEffectiveShape(side),202000):bad=True;break
    if bad:break
   if bad:continue
   points=[]
   for first,last in list(zip(path,path[1:]))+[(mid,a['common_nm']),(mid,z['common_nm'])]:
    N=math.ceil(math.dist(first,last)/25000);points.extend(v(tuple(round(i+(j-i)*(k+.5)/N) for i,j in zip(first,last))) for k in range(N))
   cov=sum(any(shp.Contains(pt) for shp in ground) for pt in points)/len(points)
   entry.update(feed_path_nm=path,tee_nm=mid,stub_to_unfitted_pad_center_mm=sep/2e6,reference_coverage=cov)
   pc['midpoint_feed_clear']+=1
   if best_ref is None or (-cov,sep)<(-best_ref['reference_coverage'],best_ref['common_pad_spacing_mm']*1e6):best_ref=entry
   if cov<1:continue
  if nearest is None or sep/1e6<nearest['common_pad_spacing_mm']:nearest=entry
  if sep>(1500000 if tee else 1150000):continue
  pairs.append(entry);break
out=dict(parent_sha256=data['sha256'],land_face=b.GetLayerName(side),module_pad_nm=start,worst_trial_trace_width_mm=.335,counts=dict(counts),referenced_feed_grid=len(dist) if bent else None,pair_counts=dict(pc),nearest_pair=nearest,best_reference=best_ref,single_obstructions=dict(near),single_accessible=len(candidates),short_candidates=candidates[:12],paired=len(pairs),best=pairs[:6],assembly_ready=False)
(root/('wifi-selector-bent-window.json' if bent else 'wifi-selector-center-window.json' if tee else 'wifi-selector-shared-window.json' if branch else 'wifi-selector-close-window.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['counts'],len(candidates),len(pairs),near.most_common(5),flush=True);os._exit(0)
