"""Make space for display chip select while retaining a nearby dedicated CPU ground via."""
from collections import Counter
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess
import pcbnew as p
from pcb_bounds import inflated_box
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda k:json.loads((root/(k+'.json')).read_text());base=read('layout-lcd-clock-trunk');src=root/base['board'];probes=read('lcd-soc-rework-obstacles')
assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']==probes['source_sha256']
b=p.LoadBoard(str(src));pin=b.FindFootprintByReference('U1').FindPadByNumber('M3');g=b.FindFootprintByReference('U1').FindPadByNumber('1F1')
ids={'7decc0c5-9db7-4f7c-aa78-220e76206bfb','a8d9e304-7786-4bf7-b003-2eac2d7e0a14'};uid=lambda o:o.m_Uuid.AsString();v=lambda xy:p.VECTOR2I(*xy)
old=[t for t in b.GetTracks() if uid(t) in ids];assert len(old)==2
for t in old:b.Remove(t)
layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
near=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if inflated_box(o,2200000).Contains(g.GetPosition())]
shapes={l:[(o.GetNetCode(),o.GetEffectiveShape(l),78200 if isinstance(o,p.PAD) and o.GetParentFootprint().GetReference()=='U1' or o.GetNetname().startswith('LPDDR4_') else 202000,o) for o in near if o.IsOnLayer(l)] for l in layers}
holes=[(o,o.GetEffectiveHoleShape()) for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
zones=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
def via(at,net):
 o=p.PCB_VIA(b);o.SetPosition(v(at));o.SetWidth(450000);o.SetDrill(200000);o.SetLayerPair(p.F_Cu,p.B_Cu);o.SetViaType(p.VIATYPE_THROUGH);o.SetNetCode(net);return o
def trace(a,z,net,width):
 t=p.PCB_TRACK(b);t.SetLayer(p.F_Cu);t.SetWidth(width);t.SetStart(v(a));t.SetEnd(v(z));t.SetNetCode(net);return t
def shorten(path):
 pts=[path[0]]
 for mid,end in zip(path[1:],path[2:]+[None]):
  if end is not None:
   a=mid[0]-pts[-1][0],mid[1]-pts[-1][1];c=end[0]-mid[0],end[1]-mid[1]
   if a[0]*c[1]==a[1]*c[0] and a[0]*c[0]+a[1]*c[1]>0:continue
  pts.append(mid)
 return pts
counts=Counter();legal_returns=[];src_xy=tuple(g.GetPosition());ground_planes=[z for z in b.Zones() if z.GetNetname()=='GND' and not z.GetIsRuleArea()]
for dx in range(-26,27):
 for dy in range(-26,27):
  at=(src_xy[0]+dx*25000,src_xy[1]+dy*25000)
  if math.dist(src_xy,at)>620000:continue
  gv=via(at,g.GetNetCode());gs=gv.GetEffectiveShape(p.F_Cu);gh=gv.GetEffectiveHoleShape()
  if gs.Collide(g.GetEffectiveShape(p.F_Cu),75000) or any(z.Collide(gs,0) for z in zones):continue
  if any(gs.Collide(o.GetEffectiveShape(p.F_Cu),75000) for o in near if isinstance(o,p.PAD) and o.IsOnLayer(p.F_Cu) and o.GetNetCode()==g.GetNetCode()):continue
  if any(n!=g.GetNetCode() and (gs.Collide(s,c) or gh.Collide(s,252000)) for l in layers for n,s,c,_ in shapes[l]):continue
  if any(gh.Collide(h,252000) or o.GetNetCode()!=g.GetNetCode() and gs.Collide(h,252000) for o,h in holes):continue
  # Do not put even same-net through lands under a BGA/passive on the rear.
  if any(isinstance(o,p.PAD) and o.IsOnLayer(p.B_Cu) and gs.Collide(o.GetEffectiveShape(p.B_Cu),75000) for o in near):continue
  if not all(any(z.HasFilledPolysForLayer(l) and z.GetFilledPolysList(l).Contains(v(at)) for z in ground_planes) for l in (p.In1_Cu,p.In4_Cu)):continue
  gt=trace(src_xy,at,g.GetNetCode(),300000);gshape=gt.GetEffectiveShape(p.F_Cu)
  if any(n!=g.GetNetCode() and gshape.Collide(s,c) for n,s,c,_ in shapes[p.F_Cu]) or any(o.GetNetCode()!=g.GetNetCode() and gshape.Collide(h,252000) for o,h in holes):continue
  legal_returns.append((at,gv,gt))
folder=root/'runs/display-cs-gnd-fanout';folder.mkdir(exist_ok=True);out=folder/src.name
for fn in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/fn,folder/fn)
winner=None;attempts=[];pairs=[]
for rec in probes['lines']['LCD_CS_N']:
 if not {r['uuid'] for r in rec['blockers']}<=ids:continue
 sv=via(rec['via_nm'],pin.GetNetCode());ss=sv.GetEffectiveShape(p.F_Cu);dh=sv.GetEffectiveHoleShape();pts=shorten(rec['signal_path_nm']);signal=[trace(a,z,pin.GetNetCode(),200000) for a,z in zip(pts,pts[1:])]
 for at,gv,gt in legal_returns:
  gs=gv.GetEffectiveShape(p.F_Cu);gh=gv.GetEffectiveHoleShape();tr=gt.GetEffectiveShape(p.F_Cu)
  if ss.Collide(gs,202000) or dh.Collide(gh,252000) or ss.Collide(gh,252000) or dh.Collide(gs,252000) or ss.Collide(tr,202000) or dh.Collide(tr,252000):continue
  if any(t.GetEffectiveShape(p.F_Cu).Collide(gt.GetEffectiveShape(p.F_Cu),202000) or t.GetEffectiveShape(p.F_Cu).Collide(gs,202000) or t.GetEffectiveShape(p.F_Cu).Collide(gh,252000) for t in signal):continue
  pairs.append((gt.GetLength(),at,gv,gt,sv,signal))
for length,at,gv,gt,sv,signal in sorted(pairs,key=lambda r:r[0]):
 items=[gv,gt,sv]+signal
 for o in items:b.Add(o)
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
 if all(r['type']=='via_dangling' and r['items']==[uid(sv)] for r in delta):
  saved=p.LoadBoard(str(out));saved.BuildConnectivity()
  gr=saved.FindFootprintByReference('U1').FindPadByNumber('1F1');sig=saved.FindFootprintByReference('U1').FindPadByNumber('M3')
  if uid(gv) in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(gr)} and uid(sv) in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(sig)} and not screen(saved):
   proof=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper=ids);winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),preservation=proof,new_drc=delta,return_nm=at,return_length_mm=length/1e6,signal_nm=tuple(sv.GetPosition()),via_uuid=uid(sv));break
 for o in items:b.Remove(o)
 attempts.append(delta)
 if len(attempts)>=12:break
(root/'display-cs-gnd-fanout.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],legal_return_sites=len(legal_returns),legal_site_pairs=len(pairs),candidate=winner,rejections=attempts,assembly_ready=False),indent=2)+'\n');print(bool(winner),len(legal_returns),len(pairs),len(attempts),flush=True);os._exit(0)
