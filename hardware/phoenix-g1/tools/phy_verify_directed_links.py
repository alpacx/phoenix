"""Verify saved input candidates, including source continuity and possible output departures."""
import hashlib,json,math,os
from pathlib import Path
import pcbnew as p
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen
study=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
source=study/'runs/input-ground-local-002/phy-joint.kicad_pcb'
base=p.LoadBoard(str(source))
conflicts=lambda b:{(v['reservation'],v['ref']) for v in screen(b)}
inherited=conflicts(base)
reports=[]
for candidate in json.loads((study/'r530-directed-link-drc.json').read_text()):
 path=study/'runs'/f"phy-directed-link-{candidate['index']}"/source.name
 b=p.LoadBoard(str(path))
 preserved=verify_preservation(base,b)
 new_conflicts=sorted(conflicts(b)-inherited)
 pad=b.FindFootprintByReference('R530').FindPadByNumber('2')
 obstacles=[t for t in b.GetTracks() if t.IsOnLayer(p.F_Cu) and t.GetNetname()!=pad.GetNetname()]
 obstacles.extend(q for f in b.GetFootprints() for q in f.Pads() if q.IsOnLayer(p.F_Cu) and q.GetNetname()!=pad.GetNetname())
 def label(o):
  return (o.GetParentFootprint().GetReference()+"."+o.GetNumber()) if isinstance(o,p.PAD) else o.GetNetname()+"/"+o.GetClass()
 shapes=[(label(o),o.GetEffectiveShape(p.F_Cu)) for o in obstacles if o.GetBoundingBox().Inflate(p.FromMM(5)).Contains(pad.GetPosition())]
 paths=[]
 blockers={}
 for dx in (-.12,0,.12):
  for dy in (-.12,0,.12):
   a=pad.GetPosition()+p.VECTOR2I(p.FromMM(dx),p.FromMM(dy))
   for angle in range(0,360,5):
    rad=math.radians(angle)
    for length in (3,2,1.5,1,.75,.5):
     z=a+p.VECTOR2I(p.FromMM(length*math.cos(rad)),p.FromMM(length*math.sin(rad)))
     t=p.PCB_TRACK(b);t.SetStart(a);t.SetEnd(z);t.SetWidth(p.FromMM(1.05));t.SetLayer(p.F_Cu)
     shape=t.GetEffectiveShape(p.F_Cu)
     hits=tuple(sorted({name for name,o in shapes if shape.Collide(o,p.FromMM(.2))}))
     if length==.5 and hits: blockers[hits]=blockers.get(hits,0)+1
     if not hits:
      paths.append(dict(start=[p.ToMM(v) for v in a],end=[p.ToMM(v) for v in z],length=length));break
 reports.append(dict(board=str(path.relative_to(study)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),preservation=preserved,new_mount_conflicts=new_conflicts,input_connected=candidate['connected'],new_drc=candidate['violations'],short_departure_blockers=[dict(items=k,count=v) for k,v in sorted(blockers.items(),key=lambda item:-item[1])],clear_output_paths=sorted(paths,key=lambda r:-r['length']),power_layout_accepted=False,assembly_ready=False))
(study/'r530-directed-link-checkpoint.json').write_text(json.dumps(reports,indent=2)+'\n')
print([(r['new_mount_conflicts'],len(r['clear_output_paths']),r['clear_output_paths'][:1]) for r in reports],flush=True)
os._exit(0)
