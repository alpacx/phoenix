"""Move U4.30's via along its unchanged straight In4 supply trunk to clear U4.31."""
from collections import Counter
from pathlib import Path
import hashlib,json,math,os,shutil,subprocess,sys
import pcbnew as p
from pcb_bounds import inflated_box
from drc_regression import introduced
from pcb_preservation import verify_preservation
sd='--sd-rail' in sys.argv
overlap='--overlap' in sys.argv or sd
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/('layout-emmc-data-power.json' if sd else 'layout-cpu-enable-bias.json')).read_text());src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
original=p.LoadBoard(str(src));b=p.LoadBoard(str(src));pm=b.FindFootprintByReference('U4')
p30=pm.FindPadByNumber('30');p31=pm.FindPadByNumber('29' if sd else '31');cap=b.FindFootprintByReference('C482').FindPadByNumber('1')
uid=lambda o:o.m_Uuid.AsString();v=lambda xy:p.VECTOR2I(*xy)
ids={'076dd4f1-e9a6-46d5-997c-079088d062f5','fc0ed385-b7cd-48d0-b72d-f220f2d4aa9b','51fcd7f0-55d1-4a19-80e5-c6edf61d6813','b2377fc2-16ac-4116-b6b0-cf47651ce134','0a51b4f5-d96c-4f41-b23c-9a8262876a4c','1f07b4d2-4ab7-45d2-883e-97a44325b443'}
items=[t for t in b.GetTracks() if uid(t) in ids];assert len(items)==6 and all(t.GetNetCode()==p30.GetNetCode() for t in items)
oldlength=sum(t.GetLength() for t in items if not isinstance(t,p.PCB_VIA) and t.GetLayer() in (p.F_Cu,p.B_Cu))
for t in items:b.Remove(t)
near=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if inflated_box(o,3500000).Contains(p31.GetPosition())]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
shapes={l:[(o.GetNetCode(),o.GetEffectiveShape(l),o.GetBoundingBox()) for o in near if o.IsOnLayer(l)] for l in layers}
holes=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in near if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
keep=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
def clean(o,layer,others=()):
 nc=o.GetNetCode();sh=o.GetEffectiveShape(layer);box=inflated_box(o,260000)
 return not any(nc!=n and box.Intersects(bb) and sh.Collide(s,202000) for n,s,bb in shapes[layer]) and not any(nc!=n and sh.Collide(h,252000) for n,h in holes) and not any(nc!=k.GetNetCode() and k.IsOnLayer(layer) and sh.Collide(k.GetEffectiveShape(layer),202000) for k in others)
def line(a,z,net,width,layer):
 t=p.PCB_TRACK(b);t.SetStart(v(a));t.SetEnd(v(z));t.SetNetCode(net);t.SetWidth(width);t.SetLayer(layer);return t
def barrel(at,net):
 t=p.PCB_VIA(b);t.SetPosition(v(at));t.SetWidth(450000);t.SetDrill(200000);t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetNetCode(net);return t
def hole_ok(t):
 h=t.GetEffectiveHoleShape();box=inflated_box(t,350000);nc=t.GetNetCode()
 return not any(nc!=n and h.Collide(g,252000) for n,g in holes) and not any(nc!=n and box.Intersects(bb) and h.Collide(g,252000) for l in layers for n,g,bb in shapes[l]) and not any(z.Collide(t.GetEffectiveShape(p.F_Cu),0) for z in keep)
def lead(q,dx,oy,x,y,w):
 start=(q.GetPosition().x+dx,q.GetBoundingBox().GetBottom()+oy);l=line(start,(x,y),q.GetNetCode(),w,p.F_Cu)
 if overlap:
  # Require a 0.100 mm wide transverse copper chord 0.025 mm inside the
  # actual terminal, sampled at 5 µm pitch, before scoring its launch.
  transverse_y=q.GetBoundingBox().GetBottom()-25000
  cross=[x for x in range(q.GetBoundingBox().GetLeft(),q.GetBoundingBox().GetRight()+1,5000) if q.HitTest(v((x,transverse_y))) and l.GetEffectiveShape(p.F_Cu).Collide(v((x,transverse_y)),0)]
  if not cross or max(cross)-min(cross)<100000:return None
 if l.GetLength() and l.GetEffectiveShape(p.F_Cu).Collide(q.GetEffectiveShape(p.F_Cu),0) and clean(l,p.F_Cu):return l
def tails(a,z,n,w,layer):
 dx=z[0]-a[0];dy=z[1]-a[1];d=min(abs(dx),abs(dy));dd=(int(math.copysign(d,dx)),int(math.copysign(d,dy)))
 for c in ((a[0]+dd[0],a[1]+dd[1]),(z[0]-dd[0],z[1]-dd[1])):
  ts=[line(u,vv,n,w,layer) for u,vv in zip((a,c),(c,z)) if u!=vv]
  if all(clean(t,layer) for t in ts):yield ts
positive=[]
for ox in range(-30000,30001,5000):
 for oy in ((-25000,0,25000,45000,60000,65000) if sd else (65000,70000,75000,80000,85000,90000)):
  for ex in (range(60700000,61350001,50000) if sd else range(61675000,62075001,50000)):
   for ey in (13100000,13200000,13300000,13400000):
    t=lead(p31,ox,oy,ex,ey,200000)
    if t is not None and t.GetLength()<=675000:positive.append(t)
positive_shapes=[t.GetEffectiveShape(p.F_Cu) for t in positive];compatibility={}
def compatible(o):
 key=(tuple(o.GetStart()),tuple(o.GetEnd()),o.GetWidth(p.F_Cu) if isinstance(o,p.PCB_VIA) else o.GetWidth())
 if key not in compatibility:
  sh=o.GetEffectiveShape(p.F_Cu);h=o.GetEffectiveHoleShape() if isinstance(o,p.PCB_VIA) else None
  compatibility[key]={ix for ix,g in enumerate(positive_shapes) if not g.Collide(sh,202000) and (h is None or not g.Collide(h,252000))}
 return compatibility[key]
counts=Counter(candidate_ldo_necks=len(positive));candidates=[];events=Counter();input_sites=set();input_necks=set();output_necks={(tuple(t.GetStart()),tuple(t.GetEnd())) for t in positive}
for x in range(60700000,62100001,25000):
 at=(x,13300000);bv=barrel(at,p30.GetNetCode())
 if not hole_ok(bv) or not all(clean(bv,l) for l in layers):continue
 counts['existing_trunk_sites']+=1
 for rear in tails(tuple(cap.GetPosition()),at,p30.GetNetCode(),300000,p.B_Cu):
  trunks=[line((57300000,13300000),at,p30.GetNetCode(),600000,p.In4_Cu),line(at,(62350000,13300000),p30.GetNetCode(),600000,p.In4_Cu)]
  for dx in (-40000,-30000,-20000,-10000,0,10000):
   for oy in (25000,45000,60000,70000):
    for ex in (x-100000,x,x+100000,61400000):
     for ey in (13000000,13050000,13100000):
      first=lead(p30,dx,oy,ex,ey,150000)
      if first is None or first.GetLength()>640000:continue
      for far in tails((ex,ey),at,p30.GetNetCode(),300000,p.F_Cu):
       rout=[first]+far+[bv]+rear+trunks
       length=sum(t.GetLength() for t in [first]+far+rear)
       if length>oldlength+200000:continue
       counts['input_loop']+=1;input_sites.add(at);input_necks.add((tuple(first.GetStart()),tuple(first.GetEnd())))
       good_ids=set.intersection(*[compatible(o) for o in [first,bv]+far]);good=[positive[ix] for ix in sorted(good_ids)]
       if not good:
        nclear=len(compatible(first));events['clears_first_only']+=bool(nclear)
        nclear=len(compatible(bv));events['clears_via_only']+=bool(nclear)
       if good:candidates.append((max(t.GetLength() for t in good),length,at,rout,good))
folder=root/('runs/ldo5-adjacent-input' if sd else 'runs/ldo6-input-overlap' if overlap else 'runs/ldo6-neighbor-input');folder.mkdir(exist_ok=True);out=folder/src.name
for fn in ('phy-joint.kicad_dru','phy-joint.kicad_pro','fp-lib-table'):shutil.copy2(src.parent/fn,folder/fn)
winner=None;attempts=[];seen=set()
for length,loop,at,rout,good in sorted(candidates,key=lambda r:(-r[0],r[1])):
 key=(at,tuple(rout[0].GetStart()),tuple(rout[0].GetEnd()))
 if key in seen:continue
 seen.add(key)
 for t in rout:b.Add(t)
 p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(out)],capture_output=True,check=True)
 delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
 if not delta:
  saved=p.LoadBoard(str(out));proof=verify_preservation(original,saved,replaced_copper=ids)
  winner=dict(board=str(out.relative_to(root)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),preservation=proof,via_nm=at,local_input_copper_mm=loop/1e6,original_local_input_copper_mm=oldlength/1e6,ldo_escapes=[(tuple(t.GetStart()),tuple(t.GetEnd())) for t in good],new_drc=delta);break
 for t in rout:b.Remove(t)
 attempts.append(delta)
 if len(seen)>=12:break
(root/('ldo5-adjacent-input.json' if sd else 'ldo6-input-overlap.json' if overlap else 'ldo6-neighbor-input.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],candidate=winner,counts=counts,geometry_count=len(candidates),terminal_overlap_gate=overlap,input_sites=sorted(input_sites),output_necks=sorted(output_necks),input_necks=sorted(input_necks),conflict_breakdown=events,rejections=attempts,assembly_ready=False),indent=2)+'\n');print(bool(winner),counts,len(candidates),flush=True);os._exit(0)
