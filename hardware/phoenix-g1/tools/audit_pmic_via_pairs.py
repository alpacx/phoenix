"""Identify exact copper objects intercepting two filled passive-land vias, for all five bucks."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import math
import os
import sys
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
folder=root/('runs/'+(sys.argv[1] if len(sys.argv)>1 else 'pmic-five-stage-full-coupled-0'));src=folder/'phy-joint.kicad_pcb';b=p.LoadBoard(str(src));layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
allitems=list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]
zones=list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()]
def audit(ref,num):
    f=b.FindFootprintByReference(ref);pin=f.FindPadByNumber(num);pos=pin.GetPosition();code=pin.GetNetCode()
    v=p.PCB_VIA(b);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetWidth(450000);v.SetDrill(200000);v.SetNetCode(code)
    items=[o for o in allitems if o.GetNetCode()!=code and inflated_box(o,1800000).Contains(pos)]
    geom=[(o,o.GetEffectiveShape(l),o.GetBoundingBox(),l) for l in layers for o in items if o.IsOnLayer(l)]
    holes=[(o,o.GetPosition(),o.GetEffectiveHoleShape()) for o in allitems if (isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x) and inflated_box(o,1800000).Contains(pos)]
    def name(o):return o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.m_Uuid.AsString()
    def failures(pt):
        v.SetPosition(p.VECTOR2I(*pt));s=v.GetEffectiveShape(p.F_Cu);h=v.GetEffectiveHoleShape();bb=inflated_box(v,400000);hit=set()
        for o,sh,box,l in geom:
            if bb.Intersects(box) and (s.Collide(sh,202000) or h.Collide(sh,250000)):hit.add((name(o),o.GetNetname(),b.GetLayerName(l)))
        for o,pt0,sh in holes:
            if bb.Contains(pt0) and h.Collide(sh,250000):hit.add((name(o),o.GetNetname(),'drill'))
        for z in zones:
            if z.GetIsRuleArea() and z.GetDoNotAllowVias() and z.Outline().Collide(s,0):hit.add((z.GetZoneName(),'keepout','keepout'))
        return hit
    pts=[]
    for dx in range(-6,7):
        for dy in range(-6,7):
            pt=pos+p.VECTOR2I(dx*75000,dy*75000)
            if all(pin.HitTest(pt+p.VECTOR2I(round(275000*math.cos(i*math.tau/32)),round(275000*math.sin(i*math.tau/32)))) for i in range(32)):
                pts.append((tuple(pt),failures(tuple(pt))))
    pairs=[]
    for i,(a,ha) in enumerate(pts):
        for z,hz in pts[:i]:
            d=math.dist(a,z)
            if 600000<=d<=1050000:
                h=ha|hz
                score=(sum(1 for ref,net,l in h if '.' in ref or net=='keepout'),len({x[0] for x in h}),-d)
                pairs.append((score,dict(vias_nm=(a,z),blockers=sorted(h))))
    pairs.sort(key=lambda r:r[0])
    return dict(ref=ref,pad=num,net=pin.GetNetname(),checked=len(pairs),best=pairs[0][1] if pairs else None)
rows=[audit(f'C4{t}{n}',pin) for n in range(1,6) for t,pin in ((2,'1'),(2,'2'),(3,'2'))]
(folder/'filled-power-pairs.json').write_text(json.dumps(dict(parent_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),rows=rows),indent=2)+'\n')
print([(r['ref']+'.'+r['pad'],list(dict.fromkeys(h[1] for h in r['best']['blockers']))) for r in rows],flush=True);os._exit(0)
