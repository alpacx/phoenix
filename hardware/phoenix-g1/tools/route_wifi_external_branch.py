"""Route from the RF selector to a shield-straddled transition and the existing U.FL port."""
from pathlib import Path
from collections import defaultdict,Counter
from functools import lru_cache
import math,heapq,hashlib,json,os,shutil,subprocess,sys
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make,barrel
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda n:json.loads((root/(n+'.json')).read_text())
cp=read('wifi-selector-branch-coupon')['candidate'];src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];narrow='--3313' in sys.argv
site=read('ufl-rf-transition-3313' if narrow else 'ufl-rf-transition-7628-wide-stitched');width=round(site['width_mm']*1e6);b=p.LoadBoard(str(src));chip=b.FindFootprintByReference('R2001').FindPadByNumber('2');code=chip.GetNetCode();origin=tuple(chip.GetPosition());rr=b.GetNetcodeFromNetname('GND');side=p.B_Cu;v=lambda xy:p.VECTOR2I(*xy)
idx={};plane={};zones={};w=make(b,origin,origin,width,code,side)
for l,ref in ((p.F_Cu,p.In1_Cu),(p.B_Cu,p.In4_Cu)):
 cell=700000;by=defaultdict(list)
 for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]:
  if o.GetNetCode()==code:continue
  bb=inflated_box(o,700000);sh=o.GetEffectiveShape(l) if o.IsOnLayer(l) else None;h=o.GetEffectiveHoleShape() if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x else None
  if sh is None and h is None:continue
  for xx in range(bb.GetLeft()//cell,bb.GetRight()//cell+1):
   for yy in range(bb.GetTop()//cell,bb.GetBottom()//cell+1):by[xx,yy].append((sh,h))
 idx[l]=by;plane[l]=[z.GetFilledPolysList(ref) for z in b.Zones() if z.GetNetname()=='GND' and z.IsOnLayer(ref) and z.HasFilledPolysForLayer(ref)]
 zones[l]=[z.Outline() for z in b.Zones() if z.IsOnLayer(l) and z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
@lru_cache(None)
def free(l,a,z):
 w.SetLayer(l);w.SetStart(v(a));w.SetEnd(v(z));sh=w.GetEffectiveShape(l);N=max(1,math.ceil(math.dist(a,z)/45000));prev=None
 for k in range(N+1):
  at=tuple(round(x+(u-x)*k/N) for x,u in zip(a,z));cellid=(at[0]//cell,at[1]//cell)
  if not any(ref.Contains(v(at)) for ref in plane[l]):return False
  if cellid!=prev:
   if any(s and sh.Collide(s,202000) or h and sh.Collide(h,252000) for s,h in idx[l][cellid]):return False
   prev=cellid
 return not any(sh.Collide(z,0) for z in zones[l])
goals=defaultdict(list);step=100000
for i,rec in enumerate(site['sites']):
 x,y=rec['via_nm']
 for dx in range(-1,2):
  for dy in range(-1,2):
   pt=((round(x/step)+dx)*step,(round(y/step)+dy)*step)
   if math.dist(pt,(x,y))<=160000:goals[pt].append(i)
seeds=[]
for ix in range(-6,7):
 for iy in range(-6,7):
  at=((round(origin[0]/step)+ix)*step,(round(origin[1]/step)+iy)*step)
  if chip.HitTest(v(at)) and math.dist(at,origin)<230000 and free(side,at,at):seeds.append(at)
dist=dict.fromkeys(seeds,0);prev={};heap=[(0,at) for at in seeds];heapq.heapify(heap);found={};lo=(42000000,4000000);hi=(77000000,35000000)
while heap:
 cost,at=heapq.heappop(heap)
 if cost!=dist[at]:continue
 for i in goals.get(at,[]):
  ep=tuple(site['sites'][i]['via_nm']);total=cost+math.dist(at,ep)+1e6*site['sites'][i]['launch_mm']
  if i not in found and free(side,at,ep):found[i]=(total,at)
 for ix,iy in ((-1,0),(1,0),(0,-1),(0,1),(1,1),(1,-1),(-1,1),(-1,-1)):
  z=(at[0]+ix*step,at[1]+iy*step);nc=cost+math.hypot(ix,iy)*step
  if nc>37000000 or not lo[0]<=z[0]<=hi[0] or not lo[1]<=z[1]<=hi[1] or nc>=dist.get(z,1e99) or not free(side,at,z):continue
  dist[z]=nc;prev[z]=at;heapq.heappush(heap,(nc,z))
frontier_file=root/'runs'/('rf-rear-reachable-'+site['stack'][-4:]+'.json')
frontier_file.write_text(json.dumps([[list(pt),list(prev[pt]) if pt in prev else None,dist[pt]] for pt in dist])+'\n')
def smooth(l,path):
 pts=[path[0]];i=0
 while i<len(path)-1:
  j=next((jj for jj in range(len(path)-1,i,-1) if free(l,path[i],path[jj])),None)
  if j is None:return None
  pts.append(path[j]);i=j
 return pts
folder=root/'runs'/('rf-external-'+site['stack'][-4:]);folder.mkdir(exist_ok=True);out=folder/src.name
for ext in ['phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table']:shutil.copy2(src.parent/ext,folder/ext)
rejected=[];winner=None
for i,(length,last) in sorted(found.items(),key=lambda row:row[1][0]):
 rec=site['sites'][i];via=tuple(rec['via_nm']);path=[last]
 while path[-1] in prev:path.append(prev[path[-1]])
 path.reverse();path.append(via);front=smooth(p.F_Cu,[tuple(at) for at in rec['launch_nm']]);rear=smooth(side,path)
 if front is None or rear is None:continue
 trial=p.LoadBoard(str(src));items=[]
 for l,pts in [(side,rear),(p.F_Cu,front)]:
  for a,z in zip(pts,pts[1:]):
   if a==z:continue
   t=make(trial,a,z,width,code,l);trial.Add(t);items.append(t.m_Uuid.AsString())
 sv=barrel(trial,via,code);trial.Add(sv)
 for xy in rec['new_return_barrels_nm']:trial.Add(barrel(trial,tuple(xy),rr))
 p.ZONE_FILLER(trial).Fill(trial.Zones());p.SaveBoard(str(out),trial);dr=folder/'drc.json';subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],capture_output=True,check=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(dr.read_text()))
 if delta and (not narrow or any(row['type']!='track_width' for row in delta)):rejected.append(dict(i=i,delta=delta));continue
 saved=p.LoadBoard(str(out));saved.BuildConnectivity();q=saved.FindFootprintByReference('J2001').FindPadByNumber('1');ids={o.m_Uuid.AsString() for o in saved.GetConnectivity().GetConnectedItems(q)}
 if saved.FindFootprintByReference('R2001').FindPadByNumber('2').m_Uuid.AsString() not in ids or screen(saved):continue
 winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),return_barrels_nm=rec['return_barrels_nm'],new_return_barrels_nm=rec['new_return_barrels_nm'],signal_via_nm=via,rear_nm=rear,front_nm=front,drc=delta);break
outdata=dict(source_sha256=cp['sha256'],stack=site['stack'],width_mm=site['width_mm'],reachable=len(dist),transition_options=len(site['sites']),reached_transitions=len(found),candidate=winner,rejected=rejected,assembly_ready=False)
(root/('wifi-external-path-'+site['stack'][-4:]+'.json')).write_text(json.dumps(outdata,indent=2)+'\n');print(site['stack'],len(dist),len(found),bool(winner),len(rejected),flush=True);os._exit(0)
