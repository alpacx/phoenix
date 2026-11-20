"""Validated auxiliary mount relocation; final caller must rerun integrated DRC."""
import pcbnew as p
from audit_mount_component_reservations import screen
MOVES={'C1661':(22.5,12),'C1674':(25,3),'C2301':(24.5,9.5)}
def apply(b):
 b.BuildConnectivity();fs={f.GetReference():f for f in b.GetFootprints()};assert 'H8104' not in fs
 for ref,xy in MOVES.items():
  f=fs[ref];assert not any(b.GetConnectivity().GetConnectedTracks(q) for q in f.Pads()),ref
  f.SetPosition(p.VECTOR2I(*(p.FromMM(v) for v in xy)))
 fs['C2301'].SetOrientationDegrees(90);fs['C2308'].Reference().SetLayer(p.B_Fab)
 z=next(z for z in b.Zones() if z.GetZoneName()=='H8104 mechanical reservation')
 box=z.GetBoundingBox();center=(p.ToMM(box.GetX()+box.GetWidth()/2),p.ToMM(box.GetY()+box.GetHeight()/2))
 assert abs(center[0]-37)<.01 and abs(center[1]-31)<.01
 z.Move(p.VECTOR2I(p.FromMM(20.25-37),p.FromMM(9-31)))
 assert not any(r['reservation']=='H8104 mechanical reservation' for r in screen(b))
 f=p.FootprintLoad('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/MountingHole.pretty','MountingHole_2.2mm_M2');assert f
 f.SetReference('H8104');f.SetAttributes(f.GetAttributes()|p.FP_BOARD_ONLY|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES);f.Reference().SetLayer(p.F_Fab);f.SetPosition(p.VECTOR2I(p.FromMM(20.25),p.FromMM(9)));b.Add(f)
 return {'moves_mm':MOVES,'reservation_from_mm':[37,31],'reservation_to_mm':[20.25,9],'drill_mm':2.2,'body_radius_mm':2.7,'reference_C2308_layer':'B.Fab','assembly_ready':False}
