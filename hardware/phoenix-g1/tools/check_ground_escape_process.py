"""Audit minimum solder-land margin and actual plane intersection at each added ground barrel."""
from pathlib import Path
from collections import Counter
import json,hashlib,math
import pcbnew as p
from pcb_bounds import inflated_box
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def load(tag):
    c=json.loads((r/(tag+'.json')).read_text());path=r/c['board'];assert hashlib.sha256(path.read_bytes()).hexdigest()==c['sha256'];return c,p.LoadBoard(str(path))
_,before=load('layout-emmc-strobe-pulldown');cp,after=load('layout-bga-ground-qualified')
old={t.m_Uuid.AsString() for t in before.GetTracks()};pads=[(f.GetReference()+'.'+q.GetNumber(),q.GetEffectiveShape(f.GetLayer()),q.GetBoundingBox()) for f in after.GetFootprints() for q in f.Pads()]
planes={l:next(z.GetFilledPolysList(l) for z in after.Zones() if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(l)) for l in (p.In1_Cu,p.In4_Cu)}
rows=[]
for v in after.GetTracks():
    if not isinstance(v,p.PCB_VIA) or v.m_Uuid.AsString() in old:continue
    assert v.GetNetname()=='GND';bb=inflated_box(v,1200000);center=v.GetPosition();shape=v.GetEffectiveShape(p.F_Cu)
    local=[(name,s) for name,s,box in pads if bb.Intersects(box)]
    lo,hi=0,1200000
    while hi-lo>1:
        mid=(lo+hi)//2
        if any(shape.Collide(s,mid) for _,s in local):hi=mid
        else:lo=mid
    near=[name for name,s in local if shape.Collide(s,hi)]
    rows.append(dict(uuid=v.m_Uuid.AsString(),xy_nm=tuple(center),land_mm=v.GetWidth(p.F_Cu)/1e6,drill_mm=v.GetDrillValue()/1e6,minimum_solder_clearance_lower_mm=lo/1e6,nearest=near,refilled_ground_planes=[after.GetLayerName(l) for l,s in planes.items() if s.Contains(center)]))
assert len(rows)==19 and all(row['minimum_solder_clearance_lower_mm']>=.100 and len(row['refilled_ground_planes'])==2 for row in rows)
(r/'bga-ground-final-solder-and-planes.json').write_text(json.dumps(dict(sha256=cp['sha256'],vias=rows,scope='Center of barrel in two filled polygons; assembly registration, plating and inductance require vendor/prototype measurements.'),indent=2)+'\n')
print(len(rows),min(row['minimum_solder_clearance_lower_mm'] for row in rows))
