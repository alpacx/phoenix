#!/usr/bin/env python3
"""CAD-derived illustrative daughterboard; not a designed LTE PCB."""
import json,math,sys
from pathlib import Path
import pcbnew as p
R=Path(__file__).resolve().parents[3];O=R/'results/hardware-render-stacked';O.mkdir(parents=True,exist_ok=True)
base=R/'hardware/phoenix-g1/migration-rk3562/experiments/stacked-expansion'
mount=json.loads((base/'mechanical/mounting-interface.json').read_text())
for variant,lift in [(sys.argv[1],0 if sys.argv[1]=='assembled' else 9)]:
 b=p.LoadBoard(str(O/'phoenix-visualization.kicad_pcb'))
 # Hide unresolved mechanical blockers only in the illustration, never in CAD source.
 hidden={r for m in mount['mounts'] for r in m['blocking_components']}
 for f in list(b.GetFootprints()):
  if f.GetReference() in hidden:b.Remove(f)
 shapes=[]
 def box(x,y,z,w,d,h,color):
  shapes.append('Transform { translation %f %f %f children [ Shape { appearance Appearance { material Material { diffuseColor %s } } geometry Box { size %f %f %f } } ] }'%(x/2.54,-y/2.54,z/2.54,color,w/2.54,d/2.54,h/2.54))
 def cylinder(x,y,z,r,h,color):
  shapes.append('Transform { translation %f %f %f rotation 1 0 0 1.570796 children [ Shape { appearance Appearance { material Material { diffuseColor %s } } geometry Cylinder { radius %f height %f } } ] }'%(x/2.54,-y/2.54,z/2.54,color,r/2.54,h/2.54))
 # Concept strip 37x9mm, 1mm PCB, no claim it fits a modem.
 box(68.5,4.5,4+lift,37,9,1,'.08 .28 .52')
 box(67.5,2.5,2.65+lift,10.6,3.38,1.7,'.12 .13 .15')
 for m in mount['mounts']:
  x,y=m['center_mm'];box(x,y,1.75,4,4,3.5,'.76 .71 .48')
  box(x,y,4.9+lift,3.8,3.8,.8,'.68 .70 .72')
  box(x,y,5.32+lift,2.4,.3,.08,'.16 .17 .18')
 # Neutral dummy components only, no specified modem footprint.
 box(61,5.2,5.05+lift,6,3,1.1,'.18 .19 .20')
 box(75.5,5.5,4.8+lift,3,2,.6,'.18 .19 .20')
 path=O/f'daughterboard-{variant}.wrl';path.write_text('#VRML V2.0 utf8\n'+'\n'.join(shapes))
 f=p.FOOTPRINT(b);f.SetReference('VISUAL_ONLY');f.SetLayer(p.F_Cu);f.SetPosition(p.VECTOR2I(0,0));m=p.FP_3DMODEL();m.m_Filename=str(path);f.Add3DModel(m);b.Add(f)
 p.SaveBoard(str(O/f'phoenix-{variant}.kicad_pcb'),b)
(O/'mockup-scope.json').write_text(json.dumps({'illustration_only':True,'dummy_daughterboard_mm':[37,9,1],'not_a_qualified_modem_board':True,'assembled_gap_mm':3.5,'exploded_additional_lift_mm':9,'hidden_unresolved_blockers':sorted(hidden),'source_CAD_unchanged':True,'mounts_not_drilled_in_actual_CAD':True},indent=2)+'\n')
