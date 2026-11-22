"""Search coordinated placements for floating bulk C1605 and a ground-connected CPU bypass."""
from pathlib import Path
from collections import Counter,defaultdict
from math import dist
import json
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'layout-ground-copper-contact.json').read_text())
b=p.LoadBoard(str(root/base['board']));b.BuildConnectivity()
side=p.B_Cu;V=lambda xy:p.VECTOR2I(*xy)
def positions(f):
    return tuple(tuple(f.FindPadByNumber(n).GetPosition()) for n in ('1','2'))
rows=[]
for ref in ('C1602','C1607','C1608'):
    cap,peer=[b.FindFootprintByReference(n) for n in ('C1605',ref)]
    original=[(tuple(f.GetPosition()),f.GetOrientationDegrees()) for f in (cap,peer)]
    origin=original[1][0]
    q=peer.FindPadByNumber('2')
    connected=b.GetConnectivity().GetConnectedTracks(q);assert len(connected)==1
    former=connected[0]
    former_real=next(t for t in b.GetTracks() if t.m_Uuid.AsString()==former.m_Uuid.AsString())
    target=max((tuple(former_real.GetStart()),tuple(former_real.GetEnd())),key=lambda xy:dist(xy,tuple(q.GetPosition())))
    box=inflated_box(peer,6500000)
    others=[f for f in b.GetFootprints() if f.GetReference() not in ('C1605',ref) and box.Intersects(f.GetBoundingBox())]
    objects=[o for o in [*b.GetTracks(),*(q for f in others for q in f.Pads())] if box.Intersects(o.GetBoundingBox()) and o.m_Uuid.AsString()!=former_real.m_Uuid.AsString()]
    courts=[f.GetCourtyard(side) for f in others if f.GetLayer()==side]
    foil=[(o.GetNetCode(),o.GetEffectiveShape(side)) for o in objects if o.IsOnLayer(side)]
    holes=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in objects if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    vias=[o.GetEffectiveShape(side) for o in objects if isinstance(o,p.PCB_VIA)]
    def clear(o):
        sh=o.GetEffectiveShape(side)
        return all(n==o.GetNetCode() or not sh.Collide(s,202000) for n,s in foil) and all((n==o.GetNetCode() and not isinstance(o,p.PAD)) or not sh.Collide(h,252000) for n,h in holes)
    def poses(f):
        result=[]
        for angle in (0,90,180,270):
            f.SetOrientationDegrees(angle)
            for i in range(-18,19):
             for j in range(-18,19):
                at=origin[0]+i*200000,origin[1]+j*200000;f.SetPosition(V(at))
                if any(f.GetCourtyard(side).Collide(s,100000) for s in courts):continue
                if any(not clear(q) or any(q.GetEffectiveShape(side).Collide(v,100000) for v in vias) for q in f.Pads()):continue
                l1,l2=positions(f)
                if f==peer and (dist(l2,target)>1800000 or not clear(make(b,l2,target,max(former_real.GetWidth(),300000),q.GetNetCode(),side))):continue
                result.append((at,angle,l1,l2))
        return result
    ps=poses(peer);cs=poses(cap);cnt=Counter();best=[]
    for at,an,pa,pz in ps:
        peer.SetOrientationDegrees(an);peer.SetPosition(V(at))
        for bt,bn,ba,bz in cs:
            if max(dist(pa,ba),dist(pz,bz))>2400000:continue
            cap.SetOrientationDegrees(bn);cap.SetPosition(V(bt))
            if cap.GetCourtyard(side).Collide(peer.GetCourtyard(side),100000):continue
            cnt['joint_placement']+=1
            paths=[make(b,pa,ba,600000,cap.FindPadByNumber('1').GetNetCode(),side),make(b,pz,bz,600000,cap.FindPadByNumber('2').GetNetCode(),side)]
            if any(not clear(t) for t in paths) or paths[0].GetEffectiveShape(side).Collide(paths[1].GetEffectiveShape(side),202000):continue
            cnt['paired_branches']+=1;best.append((at,an,bt,bn))
    rows.append(dict(peer=ref,peer_ground_restorable=len(ps),bulk_legal=len(cs),stats=cnt,best=best[:3]))
    for f,(at,an) in zip((cap,peer),original):f.SetOrientationDegrees(an);f.SetPosition(V(at))
(root/'cpu-bulk-joint-body-return-screen.json').write_text(json.dumps(dict(parent_sha256=base['sha256'],rows=rows),indent=2)+'\n')
print(rows)
