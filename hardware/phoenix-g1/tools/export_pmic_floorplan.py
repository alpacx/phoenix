"""Export the exact native courtyards, pad locations and copper near the RK809 study."""
from pathlib import Path
import hashlib
import json
import os
import pcbnew as p
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-pmic-pwron-filter.json').read_text());src=root/meta['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity()
def xy(pt):return [pt.x/1e6,pt.y/1e6]
def rect(box):return [val/1e6 for val in (box.GetLeft(),box.GetTop(),box.GetRight(),box.GetBottom())]
def poly(shape):
    res=[]
    for i in range(shape.OutlineCount()):
        chain=shape.COutline(i)
        res.append([xy(chain.CPoint(j)) for j in range(chain.PointCount())])
    return res
footprints={}
for f in b.GetFootprints():
    side=f.GetLayer();court=f.GetCourtyard(side)
    if not court.OutlineCount():continue
    footprints[f.GetReference()]=dict(side=b.GetLayerName(side),angle=f.GetOrientationDegrees(),xy=xy(f.GetPosition()),court=poly(court),bounds=rect(court.BBox()),pads=[dict(pin=q.GetNumber(),net=q.GetNetname(),xy=xy(q.GetPosition()),size=xy(q.GetSize()),angle=q.GetOrientationDegrees(),drill=xy(q.GetDrillSize()),bounds=rect(q.GetBoundingBox())) for q in f.Pads()])
box=p.BOX2I(p.VECTOR2I(40000000,0),p.VECTOR2I(48000000,30000000));tracks=[]
for t in b.GetTracks():
    if not t.GetBoundingBox().Intersects(box):continue
    via=isinstance(t,p.PCB_VIA)
    tracks.append(dict(uid=t.m_Uuid.AsString(),layer=b.GetLayerName(t.GetLayer()),net=t.GetNetname(),a=xy(t.GetStart()),z=xy(t.GetEnd()),via=via,width=(t.GetWidth(p.F_Cu) if via else t.GetWidth())/1e6))
keepouts=[]
for z in b.Zones():
    if z.GetIsRuleArea():keepouts.append(dict(name=z.GetZoneName(),bbox=rect(z.GetBoundingBox()),layers=[b.GetLayerName(l) for l in (p.F_Cu,p.B_Cu) if z.IsOnLayer(l)],tracks=z.GetDoNotAllowTracks(),vias=z.GetDoNotAllowVias(),footprints=z.GetDoNotAllowFootprints(),poly=poly(z.Outline())))
from tempfile import gettempdir
target=Path(gettempdir())/'phoenix-pmic-floorplan-native.json'
target.write_text(json.dumps(dict(sha256=meta['sha256'],footprints=footprints,tracks=tracks,keepouts=keepouts,edges=rect(b.GetBoardEdgesBoundingBox()))))
print(target,flush=True);os._exit(0)
