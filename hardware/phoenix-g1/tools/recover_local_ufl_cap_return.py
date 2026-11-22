"""Relocate the U.FL and C2009 jointly and check the capacitor return and RF copper after reload."""
from pathlib import Path
from collections import Counter
import hashlib,math,json,os,shutil,subprocess,sys
pth='--pth-safe' in sys.argv
capref='C2008' if pth else 'C2009'
wide='--clock-side' in sys.argv or pth
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import route_leg,make
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda n:json.loads((root/(n+'.json')).read_text());cp=read('wifi-selector-branch-coupon')['candidate'];probe=read('rf-local-ufl-pth-window' if pth else 'rf-local-ufl-wifi-cap-window');src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']==probe['parent_sha256'];v=lambda xy:p.VECTOR2I(*xy);uid=lambda o:o.m_Uuid.AsString();side=p.B_Cu
folder=root/'runs'/('local-ufl-pth-safe' if pth else 'local-ufl-clock-side-cap' if wide else 'local-ufl-cap-return');folder.mkdir(exist_ok=True);out=folder/src.name
for ext in ['phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table']:shutil.copy2(src.parent/ext,folder/ext)
winner=None;stats=[];orig=p.LoadBoard(str(src));frompcb=orig.FindFootprintByReference(capref);origin=tuple(frompcb.GetPosition());oldangle=frompcb.GetOrientationDegrees()
for site in probe['best']:
 if site['displaced_courtyards']!=[capref]:continue
 b=p.LoadBoard(str(src));cap=b.FindFootprintByReference(capref);j=b.FindFootprintByReference('J2001');j.Flip(j.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT);j.SetOrientationDegrees(site['angle']);j.SetPosition(v(site['pose_nm']));gb=cap.FindPadByNumber('2');sc=j.FindPadByNumber('1');sensor_gold=gb.GetNetCode()
 objs=[o for o in list(b.GetTracks())+[pad for f in b.GetFootprints() if f.GetReference()!=capref for pad in f.Pads()] if inflated_box(o,8500000).Contains(v(origin))];shapes=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in objs if o.IsOnLayer(side)];holes=[o.GetEffectiveHoleShape() for o in objs if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
 courts=[f.GetCourtyard(side) for f in b.GetFootprints() if f.GetReference()!=capref and f.GetLayer()==side and inflated_box(f,8000000).Contains(v(origin)) and f.GetCourtyard(side).OutlineCount()]
 # Replace grid stair-steps with clear native segments and maintain projected GND
 # over the final width at the centerline. No solder/land clearance is inferred.
 refs=[z.GetFilledPolysList(p.In4_Cu) for z in b.Zones() if z.GetNetname()=='GND' and z.IsOnLayer(p.In4_Cu) and z.HasFilledPolysForLayer(p.In4_Cu)]
 path=[tuple(pt) for pt in site['path_nm']];wire=make(b,path[0],path[0],338000,sc.GetNetCode(),side)
 def clear(a,z):
  wire.SetStart(v(a));wire.SetEnd(v(z));sh=wire.GetEffectiveShape(side);bb=inflated_box(wire,420000)
  if any(bb.Intersects(bo) and n!=sc.GetNetCode() and sh.Collide(s,202000) for n,s,bo in shapes) or any(sh.Collide(h,252000) for h in holes):return False
  N=max(1,math.ceil(math.dist(a,z)/25000))
  return all(any(poly.Contains(v(tuple(round(x+(y-x)*k/N) for x,y in zip(a,z)))) for poly in refs) for k in range(N+1))
 clean=[path[0]];i=0
 while i<len(path)-1:
  nxt=next((n for n in range(len(path)-1,i,-1) if clear(path[i],path[n])),None)
  if nxt is None:break
  clean.append(path[nxt]);i=nxt
 if i<len(path)-1:stats.append(dict(reason='connector shield blocks the incoming RF trace',pose=site['pose_nm']));continue
 rf=[]
 for a,z in zip(clean,clean[1:]):
  t=make(b,a,z,338000,sc.GetNetCode(),side);b.Add(t);rf.append(t)
 shapes.extend((o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in rf)
 candidates=[]
 for delta in (0,90,-90,180):
  cap.SetOrientationDegrees(oldangle+delta)
  for dx in (range(-30,31) if wide else range(-20,21)):
   for dy in (range(-30,31) if wide else range(-20,21)):
    step=200000 if wide else 100000
    at=origin[0]+dx*step,origin[1]+dy*step
    clock=tuple(b.FindFootprintByReference('U25').FindPadByNumber('10' if pth else '11').GetPosition()) if wide else origin
    if math.dist(at,origin)>(6000000 if wide else 2000000) or wide and math.dist(at,clock)>math.dist(origin,clock):continue
    cap.SetPosition(v(at));cy=cap.GetCourtyard(side)
    if any(cy.Collide(other,100000) for other in courts):continue
    valid=True
    for q in cap.Pads():
     sh=q.GetEffectiveShape(side);bb=inflated_box(q,400000)
     if any(n!=q.GetNetCode() and bb.Intersects(bo) and sh.Collide(s,202000) for n,s,bo in shapes) or any(sh.Collide(h,252000) for h in holes):valid=False;break
    if not valid:continue
    shape=gb.GetEffectiveShape(side);touch=any(n==sensor_gold and shape.Collide(sh,0) for n,sh,bb in shapes)
    candidates.append((not touch,math.dist(at,origin),at,delta))
 if not candidates:stats.append(dict(reason='no capacitor pose preserving clearance',pose=site['pose_nm']));continue
 for _,distance,at,da in sorted(candidates)[:10]:
  cap.SetOrientationDegrees(oldangle+da);cap.SetPosition(v(at));b.BuildConnectivity();
  if pth:
   cpfile=folder/'placement-scratch.kicad_pcb';p.SaveBoard(str(cpfile),b);trial=p.LoadBoard(str(cpfile))
  else:trial=b
  trialcap=trial.FindFootprintByReference(capref);trialg=trialcap.FindPadByNumber('2')
  ground=b.FindFootprintByReference('U4').FindPadByNumber('69')
  ids={uid(o) for o in b.GetConnectivity().GetConnectedItems(ground)};added=[]
  rec=dict(connected=True,kind='existing grounded copper')
  if uid(gb) not in ids:
   if not wide:continue
   rec=route_leg(trial,'GND',tuple(trialg.GetPosition()),side,tuple(trialg.GetPosition()),p.In1_Cu,300000,3.0)
   if not rec['connected']:continue
  p.ZONE_FILLER(trial).Fill(trial.Zones());p.SaveBoard(str(out),trial);dr=folder/'drc.json';subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],capture_output=True,check=True)
  delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(dr.read_text()))
  if any(r['type'] not in ('track_dangling','via_dangling') for r in delta):continue
  saved=p.LoadBoard(str(out));saved.BuildConnectivity();j2=saved.FindFootprintByReference('J2001');g=saved.FindFootprintByReference('U4').FindPadByNumber('69');gid={uid(o) for o in saved.GetConnectivity().GetConnectedItems(g)};rfset={uid(o) for o in saved.GetConnectivity().GetConnectedItems(j2.FindPadByNumber('1'))}
  if uid(saved.FindFootprintByReference(capref).FindPadByNumber('2')) not in gid or uid(saved.FindFootprintByReference('R2001').FindPadByNumber('2')) not in rfset or screen(saved):continue
  winner=dict(displaced_capacitor=capref,board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),ufl_center_nm=site['pose_nm'],ufl_angle_deg=site['angle'],cap_center_nm=at,cap_move_mm=distance/1e6,cap_rotation_deg=da,cap_restored_ground=True,cap_ground_return=rec,radio_trace_nm=clean,trace_width_mm=.338,rf_length_mm=sum(math.dist(a,z) for a,z in zip(clean,clean[1:]))/1e6,ufl_grounded={n:uid(j2.FindPadByNumber(n)) in gid for n in ('2','3')},introduced_drc=delta);break
 if winner:break
 stats.append(dict(reason='ground reconnect or DRC required',poses=len(candidates)))
(root/('rf-local-ufl-pth-safe.json' if pth else 'rf-local-ufl-clock-side-cap.json' if wide else 'rf-local-ufl-cap-return.json')).write_text(json.dumps(dict(parent_sha256=cp['sha256'],candidate=winner,attempts=stats,assembly_ready=False),indent=2)+'\n');print(bool(winner),stats[:4],flush=True);os._exit(0)
