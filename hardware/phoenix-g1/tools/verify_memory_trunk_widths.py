"""Compare original and widened native copper and filled layer references after reload."""
from pathlib import Path
import hashlib
import json
import pcbnew as p
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda name:json.loads((r/(name+'.json')).read_text())
def load(record):
    path=r/record['board'];assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256']
    return p.LoadBoard(str(path))
base=read('layout-lpddr-vddq-source');wide=read('memory-trunk-widths')
assert base['sha256']==wide['parent_sha256'] and not wide['mounts'] and not wide['new_drc']
a=load(base);z=load(wide)
idmap=lambda b:{o.m_Uuid.AsString():o for o in b.GetTracks()}
left,right=idmap(a),idmap(z)
shadows=[]
for row in wide['sections']:
    old=left[row['original']]
    l=old.GetLayer();new=[right[i] for i in row['new_ids']]
    assert old.GetStart()==new[0].GetStart() and old.GetEnd()==new[-1].GetEnd()
    assert all(u.GetEnd()==v.GetStart() for u,v in zip(new,new[1:]))
    assert all(t.GetLayer()==l and t.GetNetCode()==old.GetNetCode() and t.GetWidth()>=old.GetWidth() for t in new)
    original=p.SHAPE_POLY_SET()
    old.TransformShapeToPolygon(original,l,0,100,p.ERROR_INSIDE)
    merged=p.SHAPE_POLY_SET()
    for t in new:
        poly=p.SHAPE_POLY_SET();t.TransformShapeToPolygon(poly,l,0,100,p.ERROR_OUTSIDE)
        merged.BooleanAdd(poly)
    original.BooleanSubtract(merged)
    # 1 nm segment rounding and 100 nm arc tessellation are represented explicitly.
    shadows.append(dict(uuid=row['original'],old_copper_outside_new_mm2=original.Area()/1e12))
assert max(k['old_copper_outside_new_mm2'] for k in shadows)<.0001
def ground(b,l):
    poly=p.SHAPE_POLY_SET()
    for zone in b.Zones():
        if zone.GetNetname()=='GND' and zone.HasFilledPolysForLayer(l):
            poly.BooleanAdd(zone.GetFilledPolysList(l))
    return poly
plane=[]
for l in (p.In1_Cu,p.In4_Cu):
    al=ground(a,l);zl=ground(z,l);before=p.SHAPE_POLY_SET(al);after=p.SHAPE_POLY_SET(zl)
    before.BooleanSubtract(zl);after.BooleanSubtract(al)
    plane.append(dict(layer=a.GetLayerName(l),removed_mm2=before.Area()/1e12,added_mm2=after.Area()/1e12))
assert all(k['removed_mm2']<1e-6 and k['added_mm2']<1e-6 for k in plane)
(r/'memory-trunk-widths-projection.json').write_text(json.dumps(dict(before=base['sha256'],after=wide['sha256'],centerline_checks=shadows,filled_ground_difference=plane,assembly_ready=False),indent=2)+'\n')
print(len(shadows),max(k['old_copper_outside_new_mm2'] for k in shadows),plane)
