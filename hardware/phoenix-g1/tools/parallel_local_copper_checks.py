"""Strict checks for integrating ground/control additions and mechanical reserves."""
import json,math,pcbnew as p
from pathlib import Path
from parallel_mechanical_test import validate as mechanical_validate
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/control-routing-parallel'
def validate(b):
 mechanical_validate(b);assert not screen(b),'Component obstructs a mounting reservation'
 fs={f.GetReference():f for f in b.GetFootprints()};f=fs['H8104'];q=list(f.Pads());assert len(q)==1 and q[0].GetAttribute()==p.PAD_ATTRIB_NPTH
 assert q[0].GetDrillSize()==p.VECTOR2I(p.FromMM(2.2),p.FromMM(2.2)) and f.GetPosition()==p.VECTOR2I(p.FromMM(20.25),p.FromMM(9))
 z=next(z for z in b.Zones() if z.GetZoneName()=='H8104 mechanical reservation');box=z.GetBoundingBox()
 assert box.GetWidth()>=p.FromMM(5.4) and z.GetDoNotAllowTracks() and z.GetDoNotAllowVias() and z.GetDoNotAllowZoneFills()
 assert abs(p.ToMM(box.GetX()+box.GetWidth()/2)-20.25)<.001 and abs(p.ToMM(box.GetY()+box.GetHeight()/2)-9)<.001
 tracks={t.m_Uuid.AsString():t for t in b.GetTracks()};count=0
 for name in ['delta.json','lcd-delta.json','ground-vias-delta.json','ram-ground-vias-delta.json','middle-ground-vias-delta.json','right-ground-safe-delta.json']:
  d=json.loads((D/name).read_text())
  for q in d['tracks']:
   t=tracks[q['uuid']];assert t.GetNetname()==q['net'];assert t.GetStart()==p.VECTOR2I(*(p.FromMM(v) for v in q['start_mm']))
   if q.get('via',False):
    assert isinstance(t,p.PCB_VIA) and t.GetWidth(p.F_Cu)==p.FromMM(q['width_mm']) and t.GetDrillValue()==p.FromMM(q['drill_mm'])
    x,y=p.ToMM(t.GetPosition().x),p.ToMM(t.GetPosition().y);radius=p.ToMM(t.GetWidth(p.F_Cu))/2
    for f in b.GetFootprints():
     for pad in f.Pads():
      for layer in [p.F_Cu,p.B_Cu]:
       if not pad.IsOnLayer(layer):continue
       box=pad.GetBoundingBox(layer);dx=max(p.ToMM(box.GetX())-x,0,x-p.ToMM(box.GetRight()));dy=max(p.ToMM(box.GetY())-y,0,y-p.ToMM(box.GetBottom()))
       assert math.hypot(dx,dy)-radius>.05,('New via too close to pad',q['uuid'],f.GetReference(),pad.GetNumber())
   else:
    assert not isinstance(t,p.PCB_VIA) and t.GetWidth()==p.FromMM(q['width_mm']) and b.GetLayerName(t.GetLayer())==q['layer']
    assert t.GetEnd()==p.VECTOR2I(*(p.FromMM(v) for v in q['end_mm']))
   count+=1
 return count
