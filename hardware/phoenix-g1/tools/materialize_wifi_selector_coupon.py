"""Build the dual RF selector at the physical branch on a separate assembly-variant coupon."""
from pathlib import Path
import json,math,hashlib,os,shutil,subprocess
import pcbnew as p
from pcb_power_leg import make
from pcb_bounds import inflated_box
from drc_regression import introduced
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda n:json.loads((root/(n+'.json')).read_text());base=read('layout-usb-enable-trunk');s=read('wifi-selector-bent-window');src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']==s['parent_sha256']
folder=root/'runs/wifi-selector-branch';folder.mkdir(exist_ok=True);out=folder/src.name
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
side=p.B_Cu;v=lambda pair:p.VECTOR2I(*pair);rejected=[];winner=None
for row in [s['nearest_pair']]+s['best']:
 b=p.LoadBoard(str(src));ext=b.FindFootprintByReference('R2001');exid=ext.GetFPID();chip=b.FindFootprintByReference('U25').FindPadByNumber('2');net=chip.GetNet();new=p.NETINFO_ITEM(b,'WIFI_INT_MATCH');b.Add(new)
 # Duplicate the same land pattern for the new link. Independent UUIDs are
 # required even for fields, silk graphics and pads.
 inner=p.FOOTPRINT(ext);inner.SetUuid(p.KIID());inner.SetReference('R2005');inner.SetValue('0R INTERNAL FIT');b.Add(inner)
 for obj in list(inner.Pads())+list(inner.GraphicalItems())+list(inner.GetFields()):obj.SetUuid(p.KIID())
 inner.FindPadByNumber('1').SetNet(net);inner.FindPadByNumber('2').SetNet(new)
 for fp,key in [(ext,'first'),(inner,'second')]:
  if fp.GetLayer()!=side:fp.Flip(fp.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
  fp.SetOrientationDegrees(row[key]['angle']);fp.SetPosition(v(row[key]['pos_nm']))
  assert math.dist(tuple(fp.FindPadByNumber('1').GetPosition()),row[key]['common_nm'])<10
 origin=row['feed_path_nm'][0];ref=[z.GetFilledPolysList(p.In4_Cu) for z in b.Zones() if z.GetNetname()=='GND' and z.IsOnLayer(p.In4_Cu) and z.HasFilledPolysForLayer(p.In4_Cu)]
 near=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if o.GetNetCode()!=chip.GetNetCode() and inflated_box(o,8000000).Contains(v(origin))]
 wire=make(b,origin,origin,335000,chip.GetNetCode(),side);zones=[z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
 local=[(o.GetEffectiveShape(side),o.GetBoundingBox()) for o in near if o.IsOnLayer(side)]
 holes=[o.GetEffectiveHoleShape() for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
 def clear(a,z):
  if a==z:return True
  wire.SetStart(v(a));wire.SetEnd(v(z));shape=wire.GetEffectiveShape(side);roi=inflated_box(wire,400000)
  if any(roi.Intersects(bb) and shape.Collide(g,202000) for g,bb in local) or any(shape.Collide(h,252000) for h in holes) or any(shape.Collide(z,0) for z in zones):return False
  N=math.ceil(math.dist(a,z)/25000)
  return all(any(poly.Contains(v(tuple(round(x+(t-x)*k/N) for x,t in zip(a,z)))) for poly in ref) for k in range(N+1))
 path=[tuple(pt) for pt in row['feed_path_nm']];clean=[path[0]];i=0
 while i<len(path)-1:
  j=next((j for j in range(len(path)-1,i,-1) if clear(path[i],path[j])),None)
  if j is None:break
  clean.append(path[j]);i=j
 if i<len(path)-1:rejected.append('feed blocked');continue
 edges=list(zip(clean,clean[1:]))+[(clean[-1],tuple(row[k]['common_nm'])) for k in ('first','second')]
 if not all(clear(a,z) for a,z in edges):rejected.append('branch blocked');continue
 for a,z in edges:b.Add(make(b,a,z,335000,chip.GetNetCode(),side))
 if screen(b):rejected.append('mechanical screen');continue
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b);dr=folder/'drc.json';subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],capture_output=True,check=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(dr.read_text()))
 board=p.LoadBoard(str(out));board.BuildConnectivity();q=board.FindFootprintByReference('U25').FindPadByNumber('2');ids={obj.m_Uuid.AsString() for obj in board.GetConnectivity().GetConnectedItems(q)}
 if delta or any(board.FindFootprintByReference(n).FindPadByNumber('1').m_Uuid.AsString() not in ids for n in ('R2001','R2005')):rejected.append(dict(new_drc=delta));continue
 winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),edges_nm=edges,ext=row['first'],internal=row['second'],stub_to_unfitted_center_mm=row['stub_to_unfitted_pad_center_mm'],width_mm=.335,new_drc=delta);break
(root/'wifi-selector-branch-coupon.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=winner,rejected=rejected,assembly_ready=False),indent=2)+'\n');print(bool(winner),rejected[:2],flush=True);os._exit(0)
