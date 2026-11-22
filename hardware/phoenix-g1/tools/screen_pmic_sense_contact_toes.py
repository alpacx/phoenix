"""Examine the true outer toes of RK809 feedback pads at the adopted signal trace width."""
from pathlib import Path
from collections import Counter
import json,hashlib,math,sys
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';phy='--rgmii' in sys.argv;base=json.loads((r/('layout-rgmii-short-source-clock.json' if phy else 'layout-npu-c434-paired-load.json')).read_text());src=r/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));u=b.FindFootprintByReference('U5' if phy else 'U4');fc=p.F_Cu;V=lambda xy:p.VECTOR2I(*xy);rows=[]
for num in (('19','20','22','23','25','26','27') if phy else ('8','13','64','44','46','48')):
 q=u.FindPadByNumber(num);at=tuple(q.GetPosition());uc=tuple(u.GetPosition());dx=at[0]-uc[0];dy=at[1]-uc[1];axis=(int(math.copysign(1,dx)),0) if abs(dx)>abs(dy) else (0,int(math.copysign(1,dy)));perp=(axis[1],-axis[0]);box=inflated_box(q,2000000)
 others=[o for o in [*b.GetTracks(),*(pad for f in b.GetFootprints() for pad in f.Pads())] if o.GetNetCode()!=q.GetNetCode() and o.IsOnLayer(fc) and box.Intersects(o.GetBoundingBox())];foil=[(o.m_Uuid.AsString(),o.GetEffectiveShape(fc)) for o in others]
 names={o.m_Uuid.AsString():o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.GetNetname() for o in others}
 success=[];near=Counter()
 for radial in range(250000,500001,10000):
  for tangential in range(-100000,100001,10000):
   start=tuple(x+radial*k+tangential*t for x,k,t in zip(at,axis,perp));tip=tuple(x+300000*k for x,k in zip(start,axis))
   neck=make(b,start,tip,200000,q.GetNetCode(),fc);sh=neck.GetEffectiveShape(fc)
   # Positive overlap rather than a tangent electrical connection.
   if not q.GetEffectiveShape(fc).Collide(V(start),75000):continue
   blocks=tuple(sorted(id for id,s in foil if sh.Collide(s,202000)))
   if blocks:near[blocks]+=1
   else:success.append(start)
 rows.append(dict(pin=num,net=q.GetNetname(),direction=axis,width_mm=.20,overlap_allowance_mm=.075,launch_length_mm=.30,open_starts=len(success),examples=success[:3],nearest=[[[(k,names[k]) for k in ids],cnt] for ids,cnt in sorted(near.items(),key=lambda v:(len(v[0]),-v[1]))[:4]]))
(r/('rgmii-phy-exact-outer-toes.json' if phy else 'pmic-functional-outer-toes.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],rows=rows),indent=2)+'\n');print([(x['pin'],x['open_starts']) for x in rows])
