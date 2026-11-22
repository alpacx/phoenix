"""Screen the full antenna keepout, then save layer-specific RF reservations on a separate PCB."""
from pathlib import Path
from collections import Counter
import json,hashlib,math,os,shutil,subprocess,sys
export='--export-sites' in sys.argv
import pcbnew as p
from w3006_layout1_geometry import xy_nm,GROUND,SIGNAL,LAND_CENTERS,MARGIN,LOW,HIGH,document
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda n:json.loads((root/(n+'.json')).read_text());cp=read('wifi-selector-branch-coupon')['candidate'];src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src))
e=b.GetBoardEdgesBoundingBox();bounds=tuple(x/1e6 for x in (e.GetLeft(),e.GetTop(),e.GetRight(),e.GetBottom()));ls=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
objs=[(t.GetNetname(),t.GetBoundingBox(),[(l,t.GetEffectiveShape(l)) for l in ls if t.IsOnLayer(l)]) for t in b.GetTracks()];fps=[(f.GetReference(),f.GetCourtyard(f.GetLayer()),f.GetLayer()) for f in b.GetFootprints()];mounts=[z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName().endswith(' mechanical reservation')]
conserved=read('layout-usb-enable-trunk')['verified_pairs']
verified={q.split('.')[0] for pair in conserved for q in pair}
hard={'J1','J2','J3','U1','U2','U8001','U25'};v=lambda xy:p.VECTOR2I(*xy)
def polys(side,off,mir):
 def shape(coords):
  pol=p.SHAPE_POLY_SET();pol.NewOutline()
  for u,vv in coords:pol.Append(*xy_nm(side,off,mir,u,vv,bounds))
  return pol
 g=shape(GROUND);s=shape(SIGNAL);s.Inflate(round(MARGIN*1e6),p.CORNER_STRATEGY_ROUND_ALL_CORNERS,1000)
 # Clip the guard to the PCB boundary, preserving the same shape at each mirror/rotation.
 outline=p.SHAPE_POLY_SET();outline.NewOutline()
 for x,y in [(bounds[0],bounds[1]),(bounds[2],bounds[1]),(bounds[2],bounds[3]),(bounds[0],bounds[3])]:outline.Append(round(x*1e6),round(y*1e6))
 s.BooleanIntersection(outline);return g,s
rows=[]
b.BuildConnectivity();groupmap={};groupmembers={}
if export:
 lookup={q.m_Uuid.AsString():q for f in b.GetFootprints() for q in f.Pads() if q.GetNetCode() and q.GetNumber()}
 for uid,q in lookup.items():
  if uid in groupmap:continue
  members=sorted(({uid}|{o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(q)}) & lookup.keys())
  for k in members:groupmap[k]=members[0]
  groupmembers[members[0]]=members
 ref_members={}
 for k,q in lookup.items():ref_members.setdefault(q.GetParentFootprint().GetReference(),set()).add(k)
for side in ('top','bottom','left','right'):
 along=bounds[2]-bounds[0] if side in ('top','bottom') else bounds[3]-bounds[1]
 for i in range(math.floor((along-HIGH+LOW)/.25)+1):
  offset=i*.25
  for mir in (False,True):
   g,s=polys(side,offset,mir);bb=s.BBox();bodies=[ref for ref,shape,l in fps if shape.OutlineCount() and shape.BBox().Intersects(bb) and shape.Collide(s,0)]
   if hard.intersection(bodies) or any(k.Collide(s,0) for k in mounts):continue
   nets=Counter()
   for net,tb,shapes in objs:
    if bb.Intersects(tb) and any((g if l in (p.In1_Cu,p.In4_Cu) else s).Collide(sh,0) for l,sh in shapes):nets[net]+=1
   critical=[net for net in nets if net.startswith(('LPDDR4_','USB_TX','USB_RX','SOC_USB_','MUX_TX'))]
   rows.append(dict(side=side,offset_mm=offset,rf_face='B.Cu' if mir else 'F.Cu',components=bodies,nets=dict(nets),score=(len(critical),sum(net.startswith(('VBUS','USB_MAIN','WIFI_VBAT_SW','CPU_BUCK_LX')) for net in nets),sum(ref in verified for ref in bodies),sum(ref.startswith(('U','J','Y','L')) for ref in bodies),len(bodies),sum(nets.values()))))
if export:
 for row in rows:
  moved={uid for r in row['components'] for uid in ref_members.get(r,())};gids=set(groupmap[k] for k in moved)
  connected={k for k in moved if len(groupmembers[groupmap[k]])>1}
  row.update(connected_pad_count=len(connected),floating_pad_count=len(moved-connected),floating_components=[r for r in row['components'] if not connected.intersection(ref_members.get(r,()))],isolated_pad_rejoin_lower_bound=sum(min(len(moved.intersection(groupmembers[k])),len(groupmembers[k])-1) for k in gids),critical_conductors=[n for n in row['nets'] if n.startswith(('VBUS','USB_MAIN','LPDDR4_','USB_TX','USB_RX','SOC_USB_','WIFI_VBAT_SW','CPU_BUCK_LX','PMIC_SW'))])
 (root/'runs/w3006-edge-site-census.json').write_text(json.dumps(rows)+'\n');os._exit(0)
rows.sort(key=lambda r:r['score']);best=rows[0];side=best['side'];off=best['offset_mm'];mir=best['rf_face']=='B.Cu';g,s=polys(side,off,mir);rf=p.B_Cu if mir else p.F_Cu
def add(name,poly,layers,tracks,pours):
 z=p.ZONE(b);z.SetIsRuleArea(True);z.SetZoneName(name);z.SetDoNotAllowVias(True);z.SetDoNotAllowTracks(tracks);z.SetDoNotAllowZoneFills(pours);z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False);mask=p.LSET()
 for l in layers:mask.AddLayer(l)
 z.SetLayerSet(mask);z.Outline().AddOutline(poly.Outline(0));b.Add(z)
add('W3006 L1 exact stepped reference-plane opening',g,[p.In1_Cu,p.In4_Cu],True,True)
add('W3006 L1 signal-layer opening including right feed tail',s,[p.In2_Cu,p.In3_Cu,p.F_Cu if mir else p.B_Cu],True,True)
add('W3006 L1 RF-face opening; intentional feed and lands only',s,[rf],False,True)
# Fit the package from the two independent manufacturer land coordinates, including face
# reflection. Require both physical pad centers to register within rounding tolerance.
pkg=p.FootprintLoad(str(root.parents[0]/'internal-antenna/kicad/Phoenix_Antenna.pretty'),'W3006_Layout1');assert pkg
pkg.SetReference('AE2001');pkg.SetValue('W3006');b.Add(pkg)
if pkg.GetLayer()!=rf:pkg.Flip(pkg.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
term={n:xy_nm(side,off,mir,*uv,bounds) for n,uv in LAND_CENTERS.items()};aligned=False
for rotation in (0,90,180,270):
 pkg.SetOrientationDegrees(rotation);pkg.Move(v(term['1'])-pkg.FindPadByNumber('1').GetPosition())
 if math.dist(tuple(pkg.FindPadByNumber('2').GetPosition()),term['2'])<5:aligned=True;break
assert aligned
antnet=p.NETINFO_ITEM(b,'WIFI_INT_ANT');b.Add(antnet);pkg.FindPadByNumber('1').SetNet(antnet)
assert pkg.FindPadByNumber('2').GetNetCode()==0
folder=root/'runs/w3006-complete-reservation';folder.mkdir(exist_ok=True);out=folder/src.name
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);saved=p.LoadBoard(str(out));assert len([z for z in saved.Zones() if z.GetZoneName().startswith('W3006 L1')])==3
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
from drc_regression import introduced
delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
samples=[]
for row in rows:
 if all(row['side']!=r['side'] or abs(row['offset_mm']-r['offset_mm'])>2.8 for r in samples):samples.append(row)
 if len(samples)>=6:break
report=dict(parent_sha256=cp['sha256'],board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),dimensions=document(),candidate=best,other_sites=samples,mechanically_eligible=len(rows),new_drc=delta,rf_face_restriction='Only intentional antenna feed, matching network and floating support land may occupy this face; KiCad rule area excludes pours and vias. Existing unrelated traces/land occupancy is recorded by the screening.',land_centers_nm={n:xy_nm(side,off,mir,*xy,bounds) for n,xy in LAND_CENTERS.items()},assembly_ready=False)
(root/'w3006-complete-edge-reservation.json').write_text(json.dumps(report,indent=2)+'\n');print(best,len(rows),Counter(r['type'] for r in delta),flush=True);os._exit(0)
