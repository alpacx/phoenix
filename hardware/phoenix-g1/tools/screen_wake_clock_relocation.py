"""Search an alternate location for the buffered wake clock and its local bypass and source resistor."""
from pathlib import Path
from collections import Counter,defaultdict
import json,hashlib,math,os,sys
fine='--refine' in sys.argv
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'layout-usb-enable-trunk.json').read_text());src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256'];b=p.LoadBoard(str(src))
group={ref:b.FindFootprintByReference(ref) for ref in ('Y2001','C2007','R2003')};move=set(group)|{'Y1','C1501','C1502','R1501','R1502'}
v=lambda a:p.VECTOR2I(*a)
load=b.FindFootprintByReference('U25');pin=next(q for q in load.Pads() if q.GetNetname()=='WIFI_LPO');target=tuple(pin.GetPosition());vals={}
for layer in (p.F_Cu,p.B_Cu):
 for f in group.values():
  if f.GetLayer()!=layer:f.Flip(f.GetPosition(),p.FLIP_DIRECTION_LEFT_RIGHT)
 all_courts=[(f.GetReference(),f.GetCourtyard(layer)) for f in b.GetFootprints() if f.GetReference() not in move and f.GetLayer()==layer and f.GetCourtyard(layer).OutlineCount()]
 # Include copper belonging to the old branches. A clean site cannot rely on deleting remote
 # copper. Reconnection to the source and the supply is checked separately on an actual trial.
 objects=list(b.GetTracks())+[q for f in b.GetFootprints() if f.GetReference() not in move for q in f.Pads()]
 shapes=[(o.GetNetCode(),o.GetEffectiveShape(layer),inflated_box(o,550000)) for o in objects if o.IsOnLayer(layer)]
 holes=[(o.GetEffectiveHoleShape(),inflated_box(o,500000)) for o in objects if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
 cell=2000000;nearby=defaultdict(lambda:[[],[],[]])
 for typ,arr in enumerate((all_courts,shapes,holes)):
  for ent in arr:
   box=ent[1].BBox() if typ==0 else ent[-1]
   for ix in range((box.GetLeft()-3500000)//cell,(box.GetRight()+3500000)//cell+1):
    for iy in range((box.GetTop()-3500000)//cell,(box.GetBottom()+3500000)//cell+1):nearby[ix,iy][typ].append(ent)
 def clear(f):
  x,y=f.GetPosition();cc,ss,hh=nearby[x//cell,y//cell]

  cy=f.GetCourtyard(layer);box=cy.BBox()
  if any(cy.Collide(c,100000) for n,c in cc):return False
  for q in f.Pads():
   shape=q.GetEffectiveShape(layer);box=q.GetBoundingBox()
   if any(q.GetNetCode()!=n and box.Intersects(bx) and shape.Collide(sh,202000) for n,sh,bx in ss):return False
   if any(box.Intersects(bx) and shape.Collide(sh,252000) for sh,bx in hh):return False
  return True
 y=group['Y2001'];survive=[];counts=Counter();single=[]
 sites=[(x*1000000,yy*1000000) for x in range(18,84) for yy in range(3,38)]
 if fine:
  coarse=json.loads((root/'wake-clock-relocation-window.json').read_text())['placement'][b.GetLayerName(layer)]['oscillator_poses']
  sites=sorted({(row['pos'][0]+i*250000,row['pos'][1]+j*250000) for row in coarse for i in range(-3,4) for j in range(-3,4)})
 offsets=[(1500000,0),(-1500000,0),(0,1500000),(0,-1500000),(1200000,1200000),(-1200000,1200000),(1200000,-1200000),(-1200000,-1200000)]
 if fine:offsets=sorted(((x*250000,y*250000) for x in range(-10,11) for y in range(-10,11) if 4<=math.hypot(x,y)<=10),key=lambda off:math.hypot(*off))
 for ang in (0,90,180,270):
  y.SetOrientationDegrees(ang)
  for pos in sites:
    # Clock source must not consume the selected 24 MHz cluster envelope.
    if layer==p.F_Cu and math.dist(pos,(53000000,24250000))<5500000:continue
    if math.dist(pos,target)>24000000:continue
    y.SetPosition(v(pos))
    if not any(y.GetCourtyard(layer).Collide(c,100000) for n,c in all_courts):counts['courtyard_only']+=1
    if not clear(y):continue
    counts['oscillator_clear']+=1
    out=tuple(y.FindPadByNumber('3').GetPosition());supply=tuple(y.FindPadByNumber('4').GetPosition());ground=tuple(y.FindPadByNumber('2').GetPosition());opts={}
    for ref,anchor,padnum in [('R2003',out,'1'),('C2007',supply,'1')]:
     f=group[ref];opts[ref]=[]
     for a in (0,90,180,270):
      f.SetOrientationDegrees(a)
      for dx,dy in offsets:
       desired=(anchor[0]+dx,anchor[1]+dy);f.Move(v(desired)-f.FindPadByNumber(padnum).GetPosition());cy=f.GetCourtyard(layer)
       if cy.Collide(y.GetCourtyard(layer),100000) or not clear(f):continue
       score=math.dist(desired,anchor)+math.dist(tuple(f.FindPadByNumber('2').GetPosition()),ground if ref=='C2007' else target)
       opts[ref].append((score,tuple(f.GetPosition()),a))
    single.append(dict(pos=pos,angle=ang,series=len(opts['R2003']),bypass=len(opts['C2007'])))
    if not all(opts.values()):continue
    for sr,rp,ra in sorted(opts['R2003']):
     r=group['R2003'];r.SetOrientationDegrees(ra);r.SetPosition(v(rp))
     pick=None
     for sc,cp,ca in sorted(opts['C2007']):
      c=group['C2007'];c.SetOrientationDegrees(ca);c.SetPosition(v(cp))
      if not c.GetCourtyard(layer).Collide(r.GetCourtyard(layer),100000):pick=(sc,cp,ca);break
     if pick:
      sc,cp,ca=pick;survive.append(dict(score_mm=(sr+sc)/1e6,oscillator=[pos,ang],series=[rp,ra],bypass=[cp,ca]));break
 vals[b.GetLayerName(layer)]=dict(oscillator_poses=single,stage_counts=dict(counts),valid=len(survive),best=sorted(survive,key=lambda row:row['score_mm'])[:8])
out=dict(parent_sha256=base['sha256'],target_nm=target,placement=vals,assembly_ready=False)
(root/('wake-clock-refined-window.json' if fine else 'wake-clock-relocation-window.json')).write_text(json.dumps(out,indent=2)+'\n');print([(s,r['valid']) for s,r in vals.items()],flush=True);os._exit(0)
