#!/usr/bin/env python3
"""Make the five mechanical reservations enforceable for new copper routing.
Existing obstructing components remain explicitly unresolved; no drills created.
"""
import pcbnew as p,json,math,shutil,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'migration-rk3562/experiments/stacked-expansion';D=O/'pcb';b=p.LoadBoard(str(D/'candidate.kicad_pcb'));spec=json.loads((O/'mechanical/mounting-interface.json').read_text())
for mount in spec['mounts']+spec['auxiliary_mounts']:
 x,y=mount['center_mm'];r=mount['reserved_diameter_mm']/2/math.cos(math.pi/36)
 z=p.ZONE(b);z.SetIsRuleArea(True);z.SetZoneName(mount['ref']+' mechanical reservation');layers=p.LSET()
 for ly in [p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]:layers.AddLayer(ly)
 z.SetLayerSet(layers);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True);z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False)
 poly=z.Outline();poly.NewOutline()
 for n in range(36):
  a=2*math.pi*n/36;poly.Append(p.FromMM(x+r*math.cos(a)),p.FromMM(y+r*math.sin(a)))
 b.Add(z)
p.ZONE_FILLER(b).Fill(b.Zones());dest=D/'mount-protected.kicad_pcb';p.SaveBoard(str(dest),b)
for ext in ['kicad_pro','kicad_dru']:shutil.copy2(D/f'candidate.{ext}',dest.with_suffix('.'+ext))
(D/'mount-protected.json').write_text(json.dumps({'status':'COPPER_RESERVATIONS_ENFORCED_COMPONENT_CONFLICTS_OPEN','reserved_mounts':[m['ref'] for m in spec['mounts']+spec['auxiliary_mounts']],'all_six_copper_layers':True,'new_tracks_vias_pours_forbidden':True,'actual_drills_created':False,'component_conflicts_not_resolved':True,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'assembly_ready':False},indent=2)+'\n')
