"""Measure projected overlap between new inner rail copper and existing adjacent-layer data traces."""
import hashlib
import json
from pathlib import Path

import pcbnew as p
from pcb_bounds import inflated_box

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
def load(name):
    entry=json.loads((root/(name+'.json')).read_text())
    entry=entry.get('candidate',entry);path=root/entry['board']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']
    return p.LoadBoard(str(path)),entry['sha256']
old,base=load('layout-memory-ab4-bypass')
new,sha=load('memory-ab4-bank-bent')
previous={o.m_Uuid.AsString() for o in old.GetTracks()}
rails=[t for t in new.GetTracks() if t.m_Uuid.AsString() not in previous and not isinstance(t,p.PCB_VIA) and t.GetNetname()=='+1V1_LPDDR4' and t.GetLayer()==p.In3_Cu]
assert rails
fields=[]
for margin in (0,100000,200000,350000):
    poly=p.SHAPE_POLY_SET()
    for rail in rails:
        seg=p.SHAPE_POLY_SET();rail.TransformShapeToPolygon(seg,p.In3_Cu,margin,500,p.ERROR_OUTSIDE)
        poly.BooleanAdd(seg)
    covered=[]
    for t in old.GetTracks():
        if isinstance(t,p.PCB_VIA) or t.GetLayer()!=p.In2_Cu or not inflated_box(t,5000).Intersects(poly.BBox()):continue
        shape=p.SHAPE_POLY_SET();t.TransformShapeToPolygon(shape,p.In2_Cu,0,500,p.ERROR_OUTSIDE)
        shape.BooleanIntersection(poly)
        if shape.Area():covered.append(dict(net=t.GetNetname(),uuid=t.m_Uuid.AsString(),overlap_mm2=shape.Area()/1e12))
    fields.append(dict(margin_mm=margin/1e6,objects=covered))
result=dict(source_sha256=base,candidate_sha256=sha,fields=fields,scope='2D projection In3 onto In2, all routed nets. Does not model time-domain coupling.')
(root/'memory-ab4-bank-broadside.json').write_text(json.dumps(result,indent=2)+'\n')
print([(item['margin_mm'],[(o['net'],round(o['overlap_mm2'],4)) for o in item['objects']]) for item in fields],flush=True)
