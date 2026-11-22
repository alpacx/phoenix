"""Open an SPI data path and explicitly replace the three displaced local BGA ground returns."""
from pathlib import Path
from collections import Counter
import hashlib,heapq,json,math,os,shutil,subprocess,sys
import pcbnew as p
from pcb_bounds import inflated_box
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
keep_u3='--keep-u3' in sys.argv
site_audit='--site-audit' in sys.argv
u3_first='--u3-first' in sys.argv
read=lambda k:json.loads((root/(k+'.json')).read_text());base=read('layout-lcd-select-trunk');probes=read('lcd-mosi-u3-preserved-obstacles' if keep_u3 else 'lcd-mosi-ground-obstacles')
src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']==probes['source_sha256']
b=p.LoadBoard(str(src));cpu=b.FindFootprintByReference('U1');master=b.FindFootprintByReference('U4').FindPadByNumber('69')
sig=cpu.FindPadByNumber('T3');uid=lambda o:o.m_Uuid.AsString();v=lambda xy:p.VECTOR2I(*xy);rec=probes['lines']['LCD_MOSI'][0];assert len(rec['blockers'])==(5 if keep_u3 else 4)
ids={'6841ac21-0249-448b-b073-05b4644b1e46','7743df3c-c137-4076-8d7f-fecf0c0f2619'} if u3_first else {r['uuid'] for r in rec['blockers']};old=[t for t in b.GetTracks() if uid(t) in ids];assert all(t.GetNetname()=='GND' and (keep_u3 and isinstance(t,p.PCB_VIA) or not isinstance(t,p.PCB_VIA) and t.GetWidth()==300000) for t in old)
for t in old:b.Remove(t)
layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
def barrel(at,net):
 t=p.PCB_VIA(b);t.SetPosition(v(at));t.SetNetCode(net);t.SetWidth(450000);t.SetDrill(200000);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetViaType(p.VIATYPE_THROUGH);return t
def track(a,z,net,w):
 t=p.PCB_TRACK(b);t.SetLayer(p.F_Cu);t.SetStart(v(a));t.SetEnd(v(z));t.SetNetCode(net);t.SetWidth(w);return t
def compressed(path):
 pts=[path[0]]
 for q,n in zip(path[1:],path[2:]+[None]):
  if n:
   d=(q[0]-pts[-1][0],q[1]-pts[-1][1]);e=(n[0]-q[0],n[1]-q[1])
   if d[0]*e[1]==d[1]*e[0] and d[0]*e[0]+d[1]*e[1]>0:continue
  pts.append(q)
 return pts
sig_v=barrel(rec['via_nm'],sig.GetNetCode());
if not u3_first:b.Add(sig_v)
pts=compressed(rec['signal_path_nm'])
if not u3_first:
 for a,z in zip(pts,pts[1:]):b.Add(track(a,z,sig.GetNetCode(),200000))
grounds=[];failures=[];site_distribution={}
for num in (('U3',) if u3_first else ('1J1','1K1','1H1') if keep_u3 else ('1N3','1N2','U3')):
 q=cpu.FindPadByNumber(num);at=tuple(q.GetPosition());b.BuildConnectivity()
 near=[o for o in list(b.GetTracks())+[p0 for f in b.GetFootprints() for p0 in f.Pads()] if inflated_box(o,2300000).Contains(q.GetPosition())]
 shapes={l:[(o,o.GetEffectiveShape(l),78200 if isinstance(o,p.PAD) and o.GetParentFootprint().GetReference()=='U1' or o.GetNetname().startswith('LPDDR4_') else 202000) for o in near if o.IsOnLayer(l) and o.GetNetCode()!=q.GetNetCode()] for l in layers}
 holes=[(o,o.GetEffectiveHoleShape()) for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
 pads=[o.GetEffectiveShape(o.GetParentFootprint().GetLayer()) for o in near if isinstance(o,p.PAD)]
 keep=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
 gp=[z for z in b.Zones() if z.GetNetname()=='GND' and not z.GetIsRuleArea()]
 main={uid(o) for o in b.GetConnectivity().GetConnectedItems(master)}
 live={tuple(t.GetPosition()) for t in near if isinstance(t,p.PCB_VIA) and uid(t) in main and t.GetDrillValue()>=200000}
 t=track(at,at,q.GetNetCode(),300000);bv=barrel(at,q.GetNetCode())
 def trace_ok(a,z):
  t.SetStart(v(a));t.SetEnd(v(z));s=t.GetEffectiveShape(p.F_Cu)
  return not any(s.Collide(g,c) for _,g,c in shapes[p.F_Cu]) and not any(o.GetNetCode()!=q.GetNetCode() and s.Collide(h,252000) for o,h in holes)
 def via_ok(x):
  bv.SetPosition(v(x));s=bv.GetEffectiveShape(p.F_Cu);d=bv.GetEffectiveHoleShape()
  return not any(s.Collide(sh,c) or d.Collide(sh,252000) for l in layers for _,sh,c in shapes[l]) and not any(d.Collide(h,252000) or o.GetNetCode()!=q.GetNetCode() and s.Collide(h,252000) for o,h in holes) and not any(s.Collide(sh,75000) for sh in pads) and not any(z.Collide(s,0) for z in keep) and all(any(z.HasFilledPolysForLayer(l) and z.GetFilledPolysList(l).Contains(v(x)) for z in gp) for l in (p.In1_Cu,p.In4_Cu))
 if site_audit:
  sites=[(at[0]+x*50000,at[1]+y*50000) for x in range(-32,33) for y in range(-32,33) if math.hypot(x,y)<=32 and via_ok((at[0]+x*50000,at[1]+y*50000))]
  site_distribution[num]=dict(new_sites_nm=sites,current_sites_nm=[p0 for p0 in live if math.dist(at,p0)<1600000])
  continue
 seeds=[(at[0]+dx*25000,at[1]+dy*25000) for dx in range(-8,9) for dy in range(-8,9) if math.hypot(dx,dy)<=8 and trace_ok((at[0]+dx*25000,at[1]+dy*25000),(at[0]+dx*25000,at[1]+dy*25000))];dist=dict.fromkeys(seeds,0);queue=[(0,x) for x in seeds];heapq.heapify(queue);parents={};answer=None
 while queue:
  c,u=heapq.heappop(queue)
  if dist[u]!=c:continue
  a0=next((z for z in live if math.dist(u,z)<=150000 and trace_ok(u,z)),None)
  if a0 or via_ok(u):
   points=[u]
   while points[-1] in parents:points.append(parents[points[-1]])
   points.reverse()
   if a0 and points[-1]!=a0:points.append(a0)
   answer=compressed(points),a0 is None;break
  for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
   z=(u[0]+dx*25000,u[1]+dy*25000);g=c+math.hypot(dx,dy)*25000
   if g<=1100000 and g<dist.get(z,math.inf) and trace_ok(u,z):dist[z]=g;parents[z]=u;heapq.heappush(queue,(g,z))
 if not answer:failures.append(dict(pin=num,reachable=len(dist)));continue
 path,add=answer;new=[]
 if add:
  vv=barrel(path[-1],q.GetNetCode());new.append(vv);b.Add(vv)
 for a,z in zip(path,path[1:]):
  wire=track(a,z,q.GetNetCode(),300000);new.append(wire);b.Add(wire)
 grounds.append(dict(pin=num,new_barrel=add,at_nm=path[-1],centerline_mm=sum(math.dist(a,z) for a,z in zip(path,path[1:]))/1e6,added=[uid(o) for o in new]))
 p.ZONE_FILLER(b).Fill(b.Zones())
folder=root/('runs/display-mosi-u3-first' if u3_first else 'runs/display-mosi-u3-fanout' if keep_u3 else 'runs/display-mosi-return-fanout');folder.mkdir(exist_ok=True);out=folder/src.name
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/name,folder/name)
winner=None;delta=[]
if not failures and not site_audit:
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],check=True,capture_output=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
 if all(r['type']=='via_dangling' and r['items']==[uid(sig_v)] for r in delta):
  saved=p.LoadBoard(str(out));saved.BuildConnectivity()
  if (u3_first or uid(sig_v) in {uid(o) for o in saved.GetConnectivity().GetConnectedItems(saved.FindFootprintByReference('U1').FindPadByNumber('T3'))}) and not screen(saved):
   proof=verify_preservation(p.LoadBoard(str(src)),saved,replaced_copper=ids);winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),preservation=proof,new_drc=delta,via_uuid=uid(sig_v))
(root/('display-mosi-u3-first.json' if u3_first else 'display-mosi-available-ground-sites.json' if site_audit else 'display-mosi-u3-fanout.json' if keep_u3 else 'display-mosi-return-fanout.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=winner,returns=grounds,site_distribution=site_distribution,failed=failures,delta=delta,assembly_ready=False),indent=2)+'\n');print(bool(winner),[(r['pin'],r['centerline_mm']) for r in grounds],failures,delta,flush=True);os._exit(0)
