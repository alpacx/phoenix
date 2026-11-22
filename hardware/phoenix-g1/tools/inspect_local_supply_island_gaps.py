"""Inspect existing same-layer wide conductors on separate islands of power and ground-reference nets."""
from pathlib import Path
from collections import defaultdict
from itertools import combinations
import json,hashlib,math
import pcbnew as p
from pcb_power_leg import make
from pcb_bounds import inflated_box
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';cp=json.loads((r/'layout-bga-ground-qualified.json').read_text());src=r/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();uid=lambda o:o.m_Uuid.AsString()
pads={}
for f in b.GetFootprints():
 for q in f.Pads():pads.setdefault(f.GetReference()+'.'+q.GetNumber(),[]).append(q)
nets=[net for net in cp['open_nets'] if net.startswith(('+','VDD','VCC','VDDA','USB_AVDD','EMMC_IO','EMMC_3V3','USB_V')) and not net.endswith(('_COM','_FB'))]
positions={};by_id={};all_objects=[*b.GetTracks(),*(p for v in pads.values() for p in v)]
layers=(p.F_Cu,p.In2_Cu,p.In3_Cu,p.B_Cu);objs=defaultdict(list)
for o in b.GetTracks():objs[o.GetNetname()].append(o)
rows=[];results=[]
for net in nets:
    groups=cp['open_nets'][net];code=b.FindNet(net).GetNetCode();seeds=defaultdict(lambda:defaultdict(set))
    for i,g in enumerate(groups):
        group={uid(o) for o in b.GetConnectivity().GetConnectedItems(pads[g[0]][0])}
        for name in g:
            for o in pads[name]:
                if o.GetNetname()!=net or not (name.startswith(('C','U','L'))):continue
                for l in layers:
                    if o.IsOnLayer(l):seeds[l][i].add(tuple(o.GetPosition()))
        for t in objs[net]:
            if uid(t) not in group:continue
            if isinstance(t,p.PCB_VIA):
                if t.GetDrillValue()<300000:continue
                for l in layers:
                    if t.IsOnLayer(l):seeds[l][i].add(tuple(t.GetPosition()))
            elif t.GetLayer() in layers and t.GetWidth()>=600000:
                a,z=tuple(t.GetStart()),tuple(t.GetEnd());n=max(1,math.ceil(t.GetLength()/300000));seeds[t.GetLayer()][i].update(tuple(round(u+(v-u)*k/n) for u,v in zip(a,z)) for k in range(n+1))
    for l,gs in seeds.items():
        for (i,aa),(j,zz) in combinations(gs.items(),2):
            near=sorted((math.dist(a,z),a,z) for a in aa for z in zz if abs(a[0]-z[0])<2600000 and abs(a[1]-z[1])<2600000 and 0<math.dist(a,z)<2600000)
            if not near:continue
            bb=p.BOX2I(p.VECTOR2I(*near[0][1]),p.VECTOR2I(0,0))
            for _,a,z in near:
                bb.Merge(p.VECTOR2I(*a));bb.Merge(p.VECTOR2I(*z))
            bb.Inflate(1200000);relevant=[o for o in all_objects if o.GetNetCode()!=code and bb.Intersects(o.GetBoundingBox())]
            shapes=[(o.GetBoundingBox(),o.GetEffectiveShape(l)) for o in relevant if o.IsOnLayer(l)]
            holes=[(o.GetBoundingBox(),o.GetEffectiveHoleShape()) for o in relevant if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
            keep=[z.Outline() for z in [*b.Zones(),*(z for f in b.GetFootprints() for z in f.Zones())] if z.GetIsRuleArea() and z.IsOnLayer(l) and z.GetDoNotAllowTracks()]
            def clear(t):
                box=inflated_box(t,400000);sh=t.GetEffectiveShape(l)
                return not any(box.Intersects(bb) and sh.Collide(s,202000) for bb,s in shapes) and not any(box.Intersects(bb) and sh.Collide(s,252000) for bb,s in holes) and not any(z.Collide(sh,0) for z in keep)
            valid=None
            for _,a,z in near:
                dx,dy=z[0]-a[0],z[1]-a[1];di=min(abs(dx),abs(dy));vx,vy=int(math.copysign(di,dx)),int(math.copysign(di,dy))
                for mid in (a,(a[0]+vx,a[1]+vy),(z[0]-vx,z[1]-vy)):
                    ps=[a]+([mid] if mid not in (a,z) else [])+[z];ts=[make(b,u,v,600000,code,l) for u,v in zip(ps,ps[1:])]
                    if all(clear(t) for t in ts):valid=ps;break
                if valid:break
            rows.append(dict(net=net,source=groups[i][0],dest=groups[j][0],layer=b.GetLayerName(l),nearest_mm=near[0][0]/1e6,sites=len(near),path_nm=valid))
            if valid:results.append(rows[-1])
(r/'local-wide-power-island-gaps.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],trials=rows,solutions=results),indent=2)+'\n');print('trials',len(rows),'solutions',results)
