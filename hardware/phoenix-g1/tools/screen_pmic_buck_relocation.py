"""Find full-width same-face escape and inductor poses for four RK809 power stages."""
from pathlib import Path
import hashlib
import json
import math
import os
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-pmic-pwron-filter.json').read_text());source=root/meta['board'];assert hashlib.sha256(source.read_bytes()).hexdigest()==meta['sha256']
b=p.LoadBoard(str(source));b.BuildConnectivity();side=p.F_Cu
def probe(n,pin_id,outward):
    f=b.FindFootprintByReference('L40'+str(n));pin=b.FindFootprintByReference('U4').FindPadByNumber(pin_id);sw=f.FindPadByNumber('1');load=f.FindPadByNumber('2')
    assert sw.GetNetCode()==pin.GetNetCode() and all(not b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads())
    old_xy=tuple(f.GetPosition());old_angle=f.GetOrientationDegrees()
    pt=pin.GetPosition();dx,dy=outward
    # Retain a short 0.20 mm approach outside the existing QFN land and widen to 0.60 mm.
    objects=[o for o in list(b.GetTracks())+[q for other in b.GetFootprints() if other.GetReference()!=f.GetReference() for q in other.Pads()] if o.IsOnLayer(side) and inflated_box(o,5500000).Contains(pt)]
    geom=[(o.GetNetCode(),o.GetEffectiveShape(side),o.GetBoundingBox()) for o in objects]
    holes=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in objects if isinstance(o,p.PCB_VIA)]
    courts=[other.GetCourtyard(side) for other in b.GetFootprints() if other.GetLayer()==side and other.GetReference()!=f.GetReference() and inflated_box(other,5500000).Contains(pt)]
    keep=[z.Outline() for z in list(b.Zones())+[z for other in b.GetFootprints() for z in other.Zones()] if z.IsOnLayer(side) and z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
    def clear(o):
        s=o.GetEffectiveShape(side);bb=inflated_box(o,350000);code=o.GetNetCode()
        return not(any(code!=c and bb.Intersects(box) and s.Collide(h,202000) for c,h,box in geom) or any(code!=c and s.Collide(h,250000) for c,h in holes) or any(s.Collide(k,0) for k in keep))
    def line(a,z,w):
        t=p.PCB_TRACK(b);t.SetLayer(side);t.SetWidth(w);t.SetNetCode(pin.GetNetCode());t.SetStart(a);t.SetEnd(z);return t
    necks=[];blockers=[]
    start=pt+p.VECTOR2I(dx*440000,dy*440000)
    for length in (250000,350000,450000,500000):
        for skew in (-100000,0,100000):
            z=start+p.VECTOR2I(dx*length+dy*skew,dy*length+dx*skew)
            neck=line(start,z,200000);wide=line(z,z,600000)
            if skew==0:
                blockers.append(dict(neck_nm=length,land_contact=neck.GetEffectiveShape(side).Collide(pin.GetEffectiveShape(side),0),neck=sorted(set(o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.GetNetname() for o in objects if o.GetNetCode()!=pin.GetNetCode() and neck.GetEffectiveShape(side).Collide(o.GetEffectiveShape(side),202000))),wide=sorted(set(o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.GetNetname() for o in objects if o.GetNetCode()!=pin.GetNetCode() and wide.GetEffectiveShape(side).Collide(o.GetEffectiveShape(side),202000)))))
            if neck.GetEffectiveShape(side).Collide(pin.GetEffectiveShape(side),0) and clear(neck) and clear(wide):necks.append(z)
    options=[];counts=[0,0,0]
    for angle in (0,90,180,270):
        f.SetOrientationDegrees(angle)
        for radial in range(6,43,2):
            for lateral in range(-36,37,2):
                center=pt+p.VECTOR2I((dx*radial+dy*lateral)*100000,(dy*radial+dx*lateral)*100000);f.SetPosition(center)
                if any(f.GetCourtyard(side).Collide(c,100000) for c in courts):continue
                counts[0]+=1
                if not clear(sw) or not clear(load):continue
                counts[1]+=1
                for launch in necks:
                    end=sw.GetPosition();dd=end-launch;l=min(abs(dd.x),abs(dd.y));diag=p.VECTOR2I(int(math.copysign(l,dd.x)),int(math.copysign(l,dd.y)))
                    for corner in (launch+diag,end-diag):
                        parts=[line(a,z,600000) for a,z in ((launch,corner),(corner,end)) if a!=z]
                        if not parts or sum(t.GetLength() for t in parts)>3000000 or not all(clear(t) and not t.GetEffectiveShape(side).Collide(load.GetEffectiveShape(side),202000) for t in parts):continue
                        counts[2]+=1;options.append(dict(location_nm=tuple(center),angle=angle,neck_end_nm=tuple(launch),wide_length_mm=sum(t.GetLength() for t in parts)/1e6));break
    f.SetOrientationDegrees(old_angle);f.SetPosition(p.VECTOR2I(*old_xy))
    options.sort(key=lambda row:row['wide_length_mm']);return dict(inductor=f.GetReference(),pin=pin_id,legal_neck_exits=len(necks),central_path_obstacles=blockers,courtyard_poses=counts[0],electrical_poses=counts[1],route_options=counts[2],best_poses=options[:6])
rows=[probe(n,pin,direction) for n,pin,direction in [(1,'12',(-1,0)),(2,'9',(-1,0)),(3,'25',(0,1)),(4,'65',(0,-1))]]
(root/'pmic-four-buck-relocation.json').write_text(json.dumps(dict(parent_sha256=meta['sha256'],adopted=False,rows=rows),indent=2)+'\n')
print([(r['inductor'],r['legal_neck_exits'],r['electrical_poses'],r['route_options']) for r in rows],flush=True);os._exit(0)
