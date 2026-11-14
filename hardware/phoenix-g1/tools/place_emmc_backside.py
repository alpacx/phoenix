#!/usr/bin/env python3
"""Placement experiment. Keeps routed footprints fixed; DRC and PI review required."""
import pcbnew as p,json,math,shutil,hashlib
from pathlib import Path
from local_pcb_router import LocalRouter
R=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/emmc-system/pcb';src=R/'emmc-placement.kicad_pcb';b=p.LoadBoard(str(src));b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()};selection=json.loads((R/'emmc-floorplan-search.json').read_text());choice=selection['top_candidates'][0];refs=choice['passives_to_relocate'].copy();new=json.loads((R/'migration.json').read_text())['new_backside_positions_mm'];moves={};hold=[]
def xy(q):return p.ToMM(q.GetPosition().x),p.ToMM(q.GetPosition().y)
def setxy(f,q):f.SetPosition(p.VECTOR2I(*(p.FromMM(n) for n in q)))
def box(sh):
 r=sh.GetBoundingBox();return tuple(p.ToMM(v) for v in [r.GetX(),r.GetY(),r.GetRight(),r.GetBottom()])
def overlaps(a,z,margin=.15):return a[0]<z[2]+margin and a[2]>z[0]-margin and a[1]<z[3]+margin and a[3]>z[1]-margin
# Reserve a halo for memory bypass parts; only unrouted CPU bypass capacitors may move.
mx,my=choice['center_mm']
for ref,f in fs.items():
 if ref in refs or not ref.startswith('C16') or f.GetLayer()!=p.B_Cu:continue
 x,y=xy(f)
 if ((mx+5.5<=x<=mx+11.5 and abs(y-my)<7.5 and ref!='C1623') or ref in ['C1661','C1674']) and not any(b.GetConnectivity().GetConnectedTracks(a) for a in f.Pads()):refs.append(ref)
moving=[fs[r] for r in new if r!='U8001']+[fs[r] for r in refs]
for f in moving:
 if f.GetReference() in refs:assert not any(b.GetConnectivity().GetConnectedTracks(a) for a in f.Pads()),f.GetReference()
 moves[f.GetReference()]={'from_mm':xy(f)};b.Remove(f);hold.append(f)
assert selection['source_sha256']==hashlib.sha256(src.read_bytes()).hexdigest()
setxy(fs['U8001'],choice['center_mm']);fs['U8001'].SetOrientationDegrees(choice['orientation_degrees'])
reserved=[(53,4),(83,3),(21,3),(37,31),(70,34)]
def footprint_box(f):
 shapes=[box(s) for s in f.GraphicalItems() if s.GetLayer()==p.B_CrtYd]
 if not shapes:return None
 return min(s[0] for s in shapes),min(s[1] for s in shapes),max(s[2] for s in shapes),max(s[3] for s in shapes)
memory_center=xy(fs['U8001']);print('Memory center',memory_center,flush=True)
obstacles=[]
for other in b.GetFootprints():
 rect=footprint_box(other)
 if rect:obstacles.append((rect,.15))
 if other.Reference().IsVisible() and other.Reference().GetLayer()==p.B_SilkS:obstacles.append((box(other.Reference()),.2))
 for a in other.Pads():
  if a.GetLayerSet().Contains(p.B_Cu):obstacles.append((box(a),.25))
segments=[]
for t in b.GetTracks():
 if isinstance(t,p.PCB_VIA):obstacles.append((box(t),.3))
 elif t.GetLayer()==p.B_Cu:segments.append(((p.ToMM(t.GetStart().x),p.ToMM(t.GetStart().y)),(p.ToMM(t.GetEnd().x),p.ToMM(t.GetEnd().y)),p.ToMM(t.GetWidth())/2+.3))
def segment_distance(q,a,z):
 dx,dy=z[0]-a[0],z[1]-a[1];den=dx*dx+dy*dy;t=max(0,min(1,((q[0]-a[0])*dx+(q[1]-a[1])*dy)/den)) if den else 0
 return math.hypot(q[0]-a[0]-t*dx,q[1]-a[1]-t*dy)
def free(f):
 rect=footprint_box(f)
 if rect is None:return False
 if rect[0]<.5 or rect[1]<.5 or rect[2]>84.5 or rect[3]>34.5:return False
 if any(math.hypot(max(rect[0]-x,0,x-rect[2]),max(rect[1]-y,0,y-rect[3]))<2.7 for x,y in reserved):return False
 center=((rect[0]+rect[2])/2,(rect[1]+rect[3])/2);radius=math.hypot(rect[2]-rect[0],rect[3]-rect[1])/2
 return not any(overlaps(rect,other,margin) for other,margin in obstacles) and not any(segment_distance(center,a,z)<radius+r for a,z,r in segments)
# A bypass is not accepted merely because its body fits: reserve a nearby ground via.
vr=LocalRouter(b,(.5,.5,84.5,34.5),width=.2,grid=.25);via_forbidden=set()
for layer in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:via_forbidden|=vr.blocked(layer,'GND',.45,True)
back_blocked=vr.blocked(p.B_Cu,'GND');planned_ground_vias={}
def ground_access(f):
 pad=next(a for a in f.Pads() if a.GetNetname()=='GND');start=xy(pad)
 for dx,dy in sorted([(x*.25,y*.25) for x in range(-6,7) for y in range(-6,7)],key=lambda z:math.hypot(*z)):
  q=(round((start[0]+dx)*4)/4,round((start[1]+dy)*4)/4)
  if not .7<=math.dist(start,q)<=1.5 or not vr.within(vr.cell(q)) or vr.cell(q) in via_forbidden:continue
  if any(overlaps((q[0]-.225,q[1]-.225,q[0]+.225,q[1]+.225),other,.2) for other,_ in obstacles):continue
  if any(math.dist(q,xy(a))<.7 for a in f.Pads()):continue
  count=max(1,math.ceil(math.dist(start,q)/.1))
  if any(vr.cell((start[0]+(q[0]-start[0])*i/count,start[1]+(q[1]-start[1])*i/count)) in back_blocked for i in range(count+1)):continue
  return q
 return None
for f in moving:
 ref=f.GetReference();targets=[]
 if ref in refs:
  net=next(a.GetNetname() for a in f.Pads() if a.GetNetname() not in ('','GND'))
  targets=[xy(a) for load in ['U1','U2'] for a in fs[load].Pads() if a.GetNetname()==net]
  target=min(targets,key=lambda q:math.dist(q,xy(f))) if targets else xy(f)
 elif ref=='R8004':target=xy(next(a for a in fs['U1'].Pads() if a.GetNumber()=='M25'))
 elif ref=='C8010':target=xy(next(a for a in fs['U1'].Pads() if a.GetNumber()=='1F14'))
 else:
  local_nets={a.GetNetname() for a in f.Pads()}-{'','GND'}
  # Prefer the signal for pullups, and the dedicated rail for supply links.
  preferred=local_nets-{'EMMC_IO_1V8','EMMC_3V3','+1V8_SYS','+3V3_IO'}
  matched=preferred or local_nets
  targets=[xy(a) for a in fs['U8001'].Pads() if a.GetNetname() in matched]
  target=targets[0] if targets else (38,9)
 if ref in ['R8004','C8010']:targets=[target]
 if not targets:targets=[target]
 def target_distance(q):return min(math.dist(q,t) for t in targets)
 candidates=[(x*.5,y*.5) for x in range(4,168) for y in range(4,68)]
 found=False
 for q in sorted(candidates,key=target_distance):
  if target_distance(q)>(20 if ref.startswith('R') else 14):break
  setxy(f,q)
  if free(f):
   if ref.startswith('C80'):
    ground=ground_access(f)
    if ground is None:continue
    planned_ground_vias[ref]=ground
   found=True;break
 assert found,('No preliminary placement',ref)
 if ref.startswith('C') and ref not in planned_ground_vias:
  angles=[f.GetOrientationDegrees(),f.GetOrientationDegrees()+180];rank=[]
  for angle in angles:
   f.SetOrientationDegrees(angle);power_pad=next(a for a in f.Pads() if a.GetNetname()!='GND');rank.append((target_distance(xy(power_pad)),angle))
  f.SetOrientationDegrees(min(rank)[1])
 f.Reference().SetVisible(False);b.Add(f);obstacles.append((footprint_box(f),.25));
 if ref in planned_ground_vias:
  gx,gy=planned_ground_vias[ref];obstacles.append(((gx-.225,gy-.225,gx+.225,gy+.225),.2))
 print(ref,xy(f),flush=True);moves[ref].update(to_mm=xy(f),orientation_degrees=f.GetOrientationDegrees(),target_mm=min(targets,key=lambda t:math.dist(xy(f),t)),target_distance_mm=round(target_distance(xy(f)),3))
p.ZONE_FILLER(b).Fill(b.Zones());out=R/'emmc-repacked.kicad_pcb';p.SaveBoard(str(out),b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(src.with_suffix('.'+ext),out.with_suffix('.'+ext))
(R/'emmc-repacked.json').write_text(json.dumps({'status':'PRELIMINARY_PLACEMENT_REQUIRES_DRC_AND_PI','board_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'emmc_center_mm':memory_center,'relocated':moves,'planned_ground_vias_mm':planned_ground_vias,'placement_search_source_sha256':selection['source_sha256'],'storage_within_target_envelope_mm':[85,35],'routed_components_moved':False,'decoupling_electrically_qualified':False,'assembly_ready':False},indent=2)+'\n');print('Saved',out)
