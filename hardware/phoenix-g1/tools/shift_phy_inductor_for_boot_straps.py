"""Move L501 toward its switch source, retain the full-width trunk and discharge-capacitor tie."""
from pathlib import Path
from collections import Counter
import math,hashlib,json,subprocess,shutil
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
from drc_regression import introduced
from pcb_preservation import verify_preservation
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';base=json.loads((r/'layout-ground-copper-contact.json').read_text());src=r/base['board'];assert base['sha256']==hashlib.sha256(src.read_bytes()).hexdigest()
b=p.LoadBoard(str(src));b.BuildConnectivity();f=b.FindFootprintByReference('L501');orig=tuple(f.GetPosition());old=next(t for t in b.GetTracks() if t.m_Uuid.AsString()=='f1dd6464-b754-4958-8b4d-81fe96a54b71')
assert old.GetNetname()=='PHY_SW' and old.GetWidth()==1550000
u=tuple(old.GetStart());z=tuple(old.GetEnd());assert z==tuple(f.FindPadByNumber('1').GetPosition());b.Remove(old)
others=[g for g in b.GetFootprints() if g.GetReference()!='L501'];side=p.F_Cu
zone=inflated_box(f,3500000);parts=[g for g in others if zone.Intersects(g.GetBoundingBox())];objects=[o for o in [*b.GetTracks(),*(q for g in parts for q in g.Pads())] if zone.Intersects(o.GetBoundingBox())]
def tag(o):
    return o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.GetNetname()+' '+o.m_Uuid.AsString()
courts=[(g.GetReference(),g.GetCourtyard(side)) for g in parts if g.GetLayer()==side]
shapes=[(tag(o),o.GetNetCode(),o.GetEffectiveShape(side)) for o in objects if o.IsOnLayer(side)]
holes=[(tag(o),o.GetEffectiveHoleShape()) for o in objects if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
q1,q2=[f.FindPadByNumber(n) for n in ('1','2')];width=old.GetWidth()
toe=[(59850000,30350000),(59850000,30400000)];results=[];poses=[]
for ix in range(-5,6):
 for iy in range(-15,-3):
    at=orig[0]+ix*100000,orig[1]+iy*100000;f.SetPosition(p.VECTOR2I(*at));target=tuple(q1.GetPosition())
    tr=make(b,u,target,width,q1.GetNetCode(),side)
    if tr.GetLength()>old.GetLength():continue
    straps=[make(b,a,(a[0]-1200000,a[1]),200000,b.FindNet(n).GetNetCode(),side) for a,n in zip(toe,['PHY_CFG_LDO0','PHY_CFG_LDO1'])]
    if any(t.GetEffectiveShape(side).Collide(q.GetEffectiveShape(side),202000) for t in straps for q in (q1,q2)) or any(t.GetEffectiveShape(side).Collide(tr.GetEffectiveShape(side),202000) for t in straps):continue
    courtyard=[ref for ref,c in courts if f.GetCourtyard(side).Collide(c,100000)]
    collisions=set()
    for o in (q1,q2,tr):
        sh=o.GetEffectiveShape(side)
        collisions.update(n for n,c,s in shapes if c!=o.GetNetCode() and sh.Collide(s,202000))
        collisions.update(n for n,h in holes if sh.Collide(h,252000))
    record=dict(at=at,courtyard=courtyard,copper=sorted(collisions),switch_length_mm=tr.GetLength()/1e6)
    results.append(record)
    if not courtyard and not collisions:poses.append(record)
report=dict(parent_sha256=base['sha256'],original_switch_terminal_mm=old.GetLength()/1e6,strap_escape_both=len(results),coupled_options=len(poses),best=sorted(results,key=lambda q:(len(q['courtyard'])+len(q['copper']),q['switch_length_mm']))[:6])
(r/'phy-boot-straps-shortened-switch.json').write_text(json.dumps(report,indent=2)+'\n');print(len(results),len(poses),report['best'][:1])
