"""Screen a referenced RF transition from the fixed U.FL center pad to the module face."""
from pathlib import Path
from functools import lru_cache
from collections import Counter,defaultdict
import math,heapq,hashlib,json,os,sys
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda n:json.loads((root/(n+'.json')).read_text());cp=read('wifi-selector-branch-coupon')['candidate'];src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src));b.BuildConnectivity()
expanded='--expanded-launch' in sys.argv
add_returns='--new-returns' in sys.argv
name='JLC06161H-3313' if '--3313' in sys.argv else 'JLC06161H-7628';width=round(read('wifi-selector-impedance-model')['stacks'][name]['stack_specific_width_mm']*1e6)
v=lambda pos:p.VECTOR2I(*pos);layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu];jack=b.FindFootprintByReference('J2001');q=jack.FindPadByNumber('1');code=q.GetNetCode();origin=tuple(q.GetPosition());idx=defaultdict(list);cell=500000
objs=list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]
for o in objs:
 if not inflated_box(o,15500000 if expanded else 9500000).Contains(v(origin)):continue
 bb=inflated_box(o,650000);pad=isinstance(o,p.PAD);via=isinstance(o,p.PCB_VIA);drill=o.GetEffectiveHoleShape() if via or pad and o.GetDrillSize().x else None
 shapes={l:o.GetEffectiveShape(l) for l in layers if o.IsOnLayer(l)}
 for ix in range(bb.GetLeft()//cell,bb.GetRight()//cell+1):
  for iy in range(bb.GetTop()//cell,bb.GetBottom()//cell+1):idx[ix,iy].append((o.GetNetCode(),pad,shapes,drill))
gnid={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(jack.FindPadByNumber('2'))};groundvias=[tuple(o.GetPosition()) for o in b.GetTracks() if isinstance(o,p.PCB_VIA) and o.m_Uuid.AsString() in gnid and o.GetViaType()==p.VIATYPE_THROUGH and math.dist(tuple(o.GetPosition()),origin)<=(15000000 if expanded else 10000000)]
plane={l:[z.GetFilledPolysList(l) for z in b.Zones() if z.GetNetname()=='GND' and z.IsOnLayer(l) and z.HasFilledPolysForLayer(l)] for l in [p.In1_Cu,p.In4_Cu]}
zones=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
w=p.PCB_TRACK(b);w.SetWidth(width);w.SetNetCode(code);w.SetLayer(p.F_Cu);sig=p.PCB_VIA(b);sig.SetWidth(450000);sig.SetDrill(200000);sig.SetViaType(p.VIATYPE_THROUGH);sig.SetLayerPair(p.F_Cu,p.B_Cu)
def neighbors(at):return idx[at[0]//cell,at[1]//cell]
def covered(at,l):return any(sh.Contains(v(at)) for sh in plane[l])
@lru_cache(None)
def free(a,z):
 w.SetStart(v(a));w.SetEnd(v(z));shape=w.GetEffectiveShape(p.F_Cu)
 if any(n!=code and (p.F_Cu in sh and shape.Collide(sh[p.F_Cu],202000) or h and shape.Collide(h,252000)) for n,pad,sh,h in neighbors(a)):return False
 return all(covered(pos,p.In1_Cu) for pos in [a,z,tuple((x+y)//2 for x,y in zip(a,z))])
@lru_cache(None)
def bore(at,net=code):
 sig.SetPosition(v(at));land=sig.GetEffectiveShape(p.F_Cu);hole=sig.GetEffectiveHoleShape()
 return not any(n!=net and any(land.Collide(s,202000) or hole.Collide(s,252000) for s in sh.values()) or pad and any(land.Collide(s,52000) for s in sh.values()) or h and (land.Collide(h,252000) or hole.Collide(h,252000)) for n,pad,sh,h in neighbors(at)) and not any(z.Collide(land,0) for z in zones)
def angle(o,a,z):
 u=(a[0]-o[0],a[1]-o[1]);v=(z[0]-o[0],z[1]-o[1]);return math.degrees(math.acos(max(-1,min(1,(u[0]*v[0]+u[1]*v[1])/(math.hypot(*u)*math.hypot(*v))))))
seeds=[]
for i in range(-4,5):
 for j in range(-4,5):
  gs=100000 if expanded else 75000
  pos=(origin[0]+i*gs,origin[1]+j*gs)
  if q.HitTest(v(pos)) and free(pos,pos):seeds.append(pos)
dist=dict.fromkeys(seeds,0);prev={};queue=[(0,at) for at in seeds];heapq.heapify(queue);sites=[];counts=Counter();step=100000 if expanded else 50000
while queue:
 cost,at=heapq.heappop(queue)
 if cost!=dist[at]:continue
 if bore(at):
  counts['legal_barrel']+=1
  if covered(at,p.In4_Cu):
   counts['rear_ground']+=1;cs=[pt for pt in groundvias if 600000<=math.dist(pt,at)<=1200000]
   mates=[(a,z) for i,a in enumerate(cs) for z in cs[:i] if angle(at,a,z)>=100]
   created=set()
   if not mates and add_returns and all(math.dist(at,r['via_nm'])>350000 for r in sites):
    feed=[at]
    while feed[-1] in prev:feed.append(prev[feed[-1]])
    feedsegs=[]
    for u,t in zip(feed,feed[1:]):
     w.SetStart(v(u));w.SetEnd(v(t));feedsegs.append(w.GetEffectiveShape(p.F_Cu))
    net=b.GetNetcodeFromNetname('GND')
    for ix in range(-8,9):
     for iy in range(-8,9):
      pt=(at[0]+150000*ix,at[1]+150000*iy)
      if not 600000<=math.dist(pt,at)<=1200000 or not covered(pt,p.In1_Cu) or not covered(pt,p.In4_Cu) or not bore(pt,net):continue
      sig.SetPosition(v(pt));land=sig.GetEffectiveShape(p.F_Cu);hole=sig.GetEffectiveHoleShape()
      if any(shape.Collide(land,202000) or shape.Collide(hole,252000) for shape in feedsegs):continue
      if any(300000<math.dist(pt,k)<500000 for k in cs):continue
      cs.append(pt);created.add(pt)
    mates=[(a,z) for i,a in enumerate(cs) for z in cs[:i] if angle(at,a,z)>=100 and math.dist(a,z)>=700000]
    mates.sort(key=lambda pair:sum(g in created for g in pair))
   if mates:
    counts['return_pair_with_new_barrel' if any(pt in created for pt in mates[0]) else 'existing_return_pair']+=1
    if all(math.dist(at,r['via_nm'])>350000 for r in sites):
     path=[at]
     while path[-1] in prev:path.append(prev[path[-1]])
     sites.append(dict(via_nm=at,return_barrels_nm=mates[0],new_return_barrels_nm=[pt for pt in mates[0] if pt in created],launch_nm=list(reversed(path)),launch_mm=cost/1e6))
 for ix,iy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
  z=(at[0]+ix*step,at[1]+iy*step);nc=cost+math.hypot(ix,iy)*step
  if nc>(12500000 if expanded else 5000000) or nc>=dist.get(z,1e99) or not free(at,z):continue
  prev[z]=at;dist[z]=nc;heapq.heappush(queue,(nc,z))
out=dict(source_sha256=cp['sha256'],stack=name,width_mm=width/1e6,existing_ground_via_test_mm=[.6,1.2],straddling_angle_min_deg=100,reachable=len(dist),counts=dict(counts),sites=sites,assembly_ready=False);(root/('ufl-rf-transition-'+name[-4:]+('-wide' if expanded else '')+('-stitched' if add_returns else '')+'.json')).write_text(json.dumps(out,indent=2)+'\n');print(name,len(dist),counts,len(sites),flush=True);os._exit(0)
