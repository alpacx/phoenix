"""Place the U.FL connector on the module face inside the reachable 50-ohm rear corridor."""
from pathlib import Path
from collections import defaultdict,Counter
import math,json,hashlib,os,sys
hole_screen='--pth-courtyard' in sys.argv
release_caps='--wifi-xtal-cap-relief' in sys.argv or hole_screen
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda n:json.loads((root/(n+'.json')).read_text());cp=read('wifi-selector-branch-coupon')['candidate'];src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();jack=b.FindFootprintByReference('J2001');side=p.B_Cu;v=lambda x:p.VECTOR2I(*x)
if jack.GetLayer()!=side:jack.Flip(jack.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
sig=jack.FindPadByNumber('1');groundcode=b.GetNetcodeFromNetname('GND');gids={o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('U4').FindPadByNumber('69'))}
frontier=json.loads((root/'runs/rf-rear-reachable-7628.json').read_text());poses={tuple(row[0]):(tuple(row[1]) if row[1] else None,row[2]) for row in frontier}
other=[q for f in b.GetFootprints() if f.GetReference()!='J2001' for q in f.Pads()]+list(b.GetTracks());objects=[];holes=[];cell=1000000;idx=defaultdict(list)
for o in other:
 bb=inflated_box(o,600000);sh=o.GetEffectiveShape(side) if o.IsOnLayer(side) else None;hole=o.GetEffectiveHoleShape() if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x else None
 if not sh and not hole:continue
 for xx in range(bb.GetLeft()//cell,bb.GetRight()//cell+1):
  for yy in range(bb.GetTop()//cell,bb.GetBottom()//cell+1):idx[xx,yy].append((o.GetNetCode(),sh,hole,o.m_Uuid.AsString()))
movable={'C2008','C2009'} if release_caps else set()
courts=[(f.GetReference(),f.GetCourtyard(side)) for f in b.GetFootprints() if f.GetLayer()==side and f.GetReference()!='J2001' and f.GetCourtyard(side).OutlineCount()]
res=[z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName().endswith(' mechanical reservation')]
pth=[o for o in other if isinstance(o,p.PAD) and o.GetDrillSize().x and o.GetAttribute()==p.PAD_ATTRIB_PTH]
ok=[];counts=Counter();one=Counter();near_cases=[];byuid={o.m_Uuid.AsString():o for o in other}
for angle in (0,90,180,270):
 jack.SetOrientationDegrees(angle)
 for s,(parent,length) in poses.items():
  if length<1000000 or length>16000000 or (s[0]//100000+s[1]//100000)%2:continue
  jack.Move(v(s)-sig.GetPosition());cy=jack.GetCourtyard(side);bb=cy.BBox()
  hits=[name for name,c in courts if bb.Intersects(c.BBox()) and cy.Collide(c,100000)]
  if hits:
   if len(hits)==1:one[hits[0]]+=1
   if set(hits)-movable:continue
  if any(k.Collide(cy,0) for k in res):continue
  if hole_screen and any(cy.Collide(o.GetEffectiveShape(side),0) for o in pth if bb.Intersects(o.GetBoundingBox())):
   counts['pth_inside_courtyard']+=1;continue
  counts['mechanically_clear_footprint']+=1;contacts={};obstacles=set()
  for pad in jack.Pads():
   sh=pad.GetEffectiveShape(side);bb=pad.GetBoundingBox();near={uid:(n,shape,h) for ix in range(bb.GetLeft()//cell,bb.GetRight()//cell+1) for iy in range(bb.GetTop()//cell,bb.GetBottom()//cell+1) for n,shape,h,uid in idx[ix,iy]}
   for uid,(n,shape,h) in near.items():
    if isinstance(byuid[uid],p.PAD) and byuid[uid].GetParentFootprint().GetReference() in movable:continue
    if n!=pad.GetNetCode() and shape and sh.Collide(shape,202000) or h and sh.Collide(h,252000):obstacles.add(uid)
   if pad.GetNetCode()==groundcode:contacts[pad.GetNumber()]=[uid for uid,(n,shape,h) in near.items() if uid in gids and shape and sh.Collide(shape,0)]
  if obstacles:
   near_cases.append(dict(pose_nm=tuple(jack.GetPosition()),angle=angle,signal_nm=s,distance_mm=length/1e6,conflicts=[dict(uuid=uid,kind=byuid[uid].GetClass(),net=byuid[uid].GetNetname(),ref=byuid[uid].GetParentFootprint().GetReference() if isinstance(byuid[uid],p.PAD) else None) for uid in sorted(obstacles)],ground_contacts=contacts))
   continue
  path=[s]
  while poses[path[-1]][0]:path.append(poses[path[-1]][0])
  ok.append(dict(displaced_courtyards=hits,pose_nm=tuple(jack.GetPosition()),angle=angle,signal_nm=s,path_nm=list(reversed(path)),distance_mm=length/1e6,old_ground_contacts=contacts))
ok.sort(key=lambda r:(-sum(bool(x) for x in r['old_ground_contacts'].values()),r['distance_mm']))
out=dict(parent_sha256=cp['sha256'],counts=dict(counts),fixed_single_courtyard_obstructions=dict(one),eligible=len(ok),best_nonjack=sorted([r for r in near_cases if not any(x['ref']=='J2' for x in r['conflicts'])],key=lambda r:(len(set(x['net'] for x in r['conflicts'])),len(r['conflicts']),r['distance_mm']))[:4],best_bounded=sorted(near_cases,key=lambda r:(len(set(x['net'] for x in r['conflicts'])),len(r['conflicts']),r['distance_mm']))[:8],best=ok if hole_screen else ok[:12],assembly_ready=False)
(root/('rf-local-ufl-pth-window.json' if hole_screen else 'rf-local-ufl-wifi-cap-window.json' if release_caps else 'rf-local-ufl-placement.json')).write_text(json.dumps(out,indent=2)+'\n');print(counts,one.most_common(4),len(ok),flush=True);os._exit(0)
