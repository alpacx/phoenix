"""Find legal off-land access from the RK809 DDR feedback pad on the complete PCB."""
import hashlib
import json
import math
import os
import sys
from pathlib import Path
import pcbnew as p
from pcb_bounds import inflated_box, point_distance_squared

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
debug=next((n for n in ('DEBUG_RX','DEBUG_TX') if n in sys.argv),None)
vdc='--vdc' in sys.argv
cp=json.loads((root/('layout-cpu-load-sense.json' if debug else 'layout-aux-cap-banks.json' if vdc else 'layout-ground-island-barrels.json')).read_text())
src=root/cp['board']
assert cp['sha256']==hashlib.sha256(src.read_bytes()).hexdigest()
b=p.LoadBoard(str(src))
q=b.FindFootprintByReference('U4').FindPadByNumber('61' if vdc else '27')
if debug:q=next(q for q in b.FindFootprintByReference('U1').Pads() if q.GetNetname()==debug)
start=q.GetPosition()
layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
obs=[k for k in list(b.GetTracks())+[pad for f in b.GetFootprints() for pad in f.Pads()] if inflated_box(k,3950000 if debug else 2700000).Contains(start) and k.GetNetCode()!=q.GetNetCode()]
shapes={l:[(o.GetEffectiveShape(l),o.GetBoundingBox()) for o in obs if o.IsOnLayer(l)] for l in layers}
holes=[k.GetEffectiveHoleShape() for k in obs if isinstance(k,p.PCB_VIA)]
t=p.PCB_TRACK(b)
t.SetWidth(200000)
t.SetLayer(p.F_Cu)
v=p.PCB_VIA(b)
v.SetViaType(p.VIATYPE_THROUGH)
v.SetLayerPair(p.F_Cu,p.B_Cu)
v.SetWidth(450000)
v.SetDrill(200000)
def clear(item,l):
    s=item.GetEffectiveShape(l)
    box=inflated_box(item,250000)
    if any(s.Collide(h,250000) for h in holes):return False
    return not any(box.Intersects(bb) and s.Collide(o,200000) for o,bb in shapes[l])
sites=[]
radius=55 if debug else 28
for ix in range(-radius,radius+1):
    for iy in range(-radius,radius+1):
        pos=start+p.VECTOR2I(ix*50000,iy*50000)
        v.SetPosition(pos)
        if any(not clear(v,l) for l in layers):continue
        hole=v.GetEffectiveHoleShape()
        if any(hole.Collide(s,250000) for l in layers for s,box in shapes[l] if point_distance_squared(box,pos)<500000**2):continue
        if q.GetEffectiveShape(p.F_Cu).Collide(v.GetEffectiveShape(p.F_Cu),100000):continue
        if any(z.GetIsRuleArea() and z.GetDoNotAllowVias() and inflated_box(z,225000).Contains(pos) for z in b.Zones()):continue
        choices=[]
        ends=[(0,dy) for dy in (350000,375000,400000,435000,440000,445000,450000,-350000,-375000,-400000,-435000,-440000,-445000,-450000)]
        if debug:ends=[(0,0),(75000,0),(-75000,0),(0,75000),(0,-75000)]
        for dx,dy in ends:
            toe=start+p.VECTOR2I(dx,dy)
            d=pos-toe
            diag=min(abs(d.x),abs(d.y))
            step=p.VECTOR2I(int(math.copysign(diag,d.x)),int(math.copysign(diag,d.y)))
            for c in (toe+step,pos-step):
                for a,g in ((toe,c),(c,pos)):
                    t.SetStart(a);t.SetEnd(g)
                    if a!=g and not clear(t,p.F_Cu):break
                else:choices.append(((c-toe).EuclideanNorm()+(pos-c).EuclideanNorm(),(tuple(toe),tuple(c),tuple(pos))))
        if choices:
            length,path=min(choices)
            sites.append(dict(path_nm=path,length_mm=length/1e6))
(root/(debug.lower()+'-access.json' if debug else 'pmic-vdc-access.json' if vdc else 'pmic-feedback-access.json')).write_text(json.dumps(dict(source_sha256=cp['sha256'],pin=q.GetParentFootprint().GetReference()+'.'+q.GetNumber(),via_land_drill_mm=[.45,.2],width_mm=.2,sites=sorted(sites,key=lambda s:s['length_mm']),assembly_ready=False),indent=2)+'\n')
print(len(sites),sorted(sites,key=lambda s:s['length_mm'])[:1],flush=True)
os._exit(0)
