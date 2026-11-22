"""Measure the eMMC DAT0 copper's adjacent ground planes and via-return geometry."""
from pathlib import Path
import hashlib,json,math
import pcbnew as p
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
entry=json.loads((root/'emmc-d0-data-pullup.json').read_text())['candidate'];src=root/entry['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==entry['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
uid=lambda o:o.m_Uuid.AsString()
ground={uid(o) for o in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('U4').FindPadByNumber('69'))}
returns=[t for t in b.GetTracks() if uid(t) in ground and isinstance(t,p.PCB_VIA) and t.GetViaType()==p.VIATYPE_THROUGH]
planes={}
for layer in (p.In1_Cu,p.In4_Cu):
    plane=p.SHAPE_POLY_SET()
    for z in b.Zones():
        if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(layer):plane.BooleanAdd(z.GetFilledPolysList(layer))
    planes[layer]=plane
rows=[];vias=[]
for t in b.GetTracks():
    if t.GetNetname()!='EMMC_D0':continue
    if isinstance(t,p.PCB_VIA):
        ret=min(returns,key=lambda g:math.dist(tuple(g.GetPosition()),tuple(t.GetPosition())))
        vias.append(dict(via=uid(t),nearest_gnd=uid(ret),distance_mm=math.dist(tuple(ret.GetPosition()),tuple(t.GetPosition()))/1e6));continue
    layer=t.GetLayer();ref={p.F_Cu:p.In1_Cu,p.In2_Cu:p.In1_Cu,p.In3_Cu:p.In4_Cu,p.B_Cu:p.In4_Cu}[layer]
    poly=p.SHAPE_POLY_SET();t.TransformShapeToPolygon(poly,layer,0,500,p.ERROR_OUTSIDE);poly.BooleanSubtract(planes[ref])
    n=max(1,math.ceil(t.GetLength()/25000));gap=[];run=0
    a=tuple(t.GetStart());z=tuple(t.GetEnd())
    for i in range(n+1):
        at=p.VECTOR2I(*(round(x+(y-x)*i/n) for x,y in zip(a,z)))
        if planes[ref].Contains(at):run=0
        else:run+=1
        gap.append(run)
    rows.append(dict(id=uid(t),layer=b.GetLayerName(layer),start_nm=a,end_nm=z,length_mm=t.GetLength()/1e6,missing_mm2=poly.Area()/1e12,max_centerline_gap_mm=min(t.GetLength()/1e6,max(gap)*t.GetLength()/n/1e6)))
res=dict(sha256=entry['sha256'],length_mm=sum(row['length_mm'] for row in rows),rows=rows,vias=vias,scope='CAD plane overlap at trace width and sampled centerline; via antipads included, signal integrity and timing unmeasured.')
(root/'emmc-d0-reference.json').write_text(json.dumps(res,indent=2)+'\n')
print(res['length_mm'],[x['distance_mm'] for x in vias],max(x['max_centerline_gap_mm'] for x in rows))
