"""Find practical same-face 24 MHz crystal locations close to the SoC oscillator pads."""
from collections import Counter
from pathlib import Path
import json,math,hashlib,os,sys
back='--rear-face' in sys.argv
release_wake='--relocate-wake-oscillator' in sys.argv
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
d=json.loads((root/'layout-usb-enable-trunk.json').read_text());src=root/d['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==d['sha256'];b=p.LoadBoard(str(src))
soc=b.FindFootprintByReference('U1');sinks=[tuple(soc.FindPadByNumber(pin).GetPosition()) for pin in ('AG25','AF25')]
moving={'Y1','R1501','R1502','C1501','C1502'}
if release_wake:moving.add('Y2001')
y=b.FindFootprintByReference('Y1');side=p.B_Cu if back else p.F_Cu
if back:y.Flip(y.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
fpts=[f for f in b.GetFootprints() if f.GetReference() not in moving and inflated_box(f,14000000).Contains(p.VECTOR2I(*sinks[0]))]
courts=[(f.GetReference(),f.GetCourtyard(side)) for f in fpts if f.GetLayer()==side and f.GetCourtyard(side).OutlineCount()]
obj=[o for o in list(b.GetTracks())+[q for f in fpts for q in f.Pads()] if o.IsOnLayer(side) and inflated_box(o,13500000).Contains(p.VECTOR2I(*sinks[0]))]
shapes=[(o.GetNetCode(),o.GetNetname(),o.GetEffectiveShape(side),inflated_box(o,525000)) for o in obj]
holes=[(o.GetEffectiveHoleShape(),inflated_box(o,500000)) for o in obj if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
valid=[];conflicts=Counter();total=0;toponly=[]
for angle in (0,90,180,270):
 y.SetOrientationDegrees(angle)
 for dx in range(-36,37):
  for dy in range(-36,37):
   x=sinks[0][0]+dx*250000;ypos=sinks[0][1]+dy*250000
   y.SetPosition(p.VECTOR2I(x,ypos));pads=list(y.Pads());anchors=[tuple(y.FindPadByNumber(pin).GetPosition()) for pin in ('1','3')]
   lengths=[math.dist(pt,ref)/1e6 for pt,ref in zip(anchors,sinks)]
   if max(lengths)>8:continue
   total+=1;court=y.GetCourtyard(side);bb=court.BBox()
   coll=frozenset(ref for ref,sh in courts if court.Collide(sh,100000))
   if coll:conflicts[tuple(sorted(coll))]+=1;continue
   hits=set()
   for q in pads:
    box=q.GetBoundingBox();sh=q.GetEffectiveShape(side)
    for n,name,g,box2 in shapes:
     if n!=q.GetNetCode() and box.Intersects(box2) and sh.Collide(g,202000):hits.add(name)
    if any(box.Intersects(box2) and sh.Collide(h,252000) for h,box2 in holes):hits.add('drilled hole')
   if hits:toponly.append(dict(center_nm=[x,ypos],angle=angle,leads_mm=lengths,nets=sorted(hits)));continue
   valid.append(dict(center_nm=[x,ypos],angle=angle,leads_mm=lengths))
rank=lambda v:(max(v['leads_mm']),sum(v['leads_mm']))
out=dict(parent_sha256=d['sha256'],evaluated=total,free_poses=len(valid),best_free=sorted(valid,key=rank)[:8],courtyard_only_free=len(toponly),near_clear=sorted(toponly,key=lambda v:(len(v['nets']),rank(v)))[:8],single_courtyard_blockers={k[0]:n for k,n in conflicts.items() if len(k)==1},assembly_ready=False)
o=p.LoadBoard(str(src));orig=o.FindFootprintByReference('Y1')
out['existing_lead_lower_bounds_mm']=[math.dist(tuple(orig.FindPadByNumber(pin).GetPosition()),ref)/1e6 for pin,ref in zip(('1','3'),sinks)]
(root/('soc-crystal-rear-window.json' if back else 'soc-crystal-wake-window.json' if release_wake else 'soc-crystal-floorplan-window.json')).write_text(json.dumps(out,indent=2)+'\n');print(total,len(valid),len(toponly),out['best_free'][:1],out['near_clear'][:1],flush=True);os._exit(0)
