"""Keep the original return anchors while shifting the one barrel obstructing C2303."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import pcbnew as p
from audit_mount_component_reservations import screen
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from drc_regression import introduced

stage=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
read=lambda name:json.loads((stage/name).read_text())
source=read('layout-lpddr-vdd1-bank.json')
cases=read('vdd1-c2303-obstructions.json')
src=stage/source['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==source['sha256']==cases['parent_sha256']
case=next(row for row in cases['shortest_obstructions'] if len(row['blockers'])==1 and row['blockers'][0][1:3]==['PCB_VIA','GND'])
b=p.LoadBoard(str(src))
uid=lambda obj:obj.m_Uuid.AsString()
via=next(t for t in b.GetTracks() if uid(t)==case['blockers'][0][0])
origin=tuple(via.GetPosition())
legs=[(t,tuple(t.GetStart())==origin) for t in b.GetTracks() if not isinstance(t,p.PCB_VIA) and origin in (tuple(t.GetStart()),tuple(t.GetEnd()))]
assert len(legs)==3 and all(t.GetNetname()=='GND' for t,_ in legs)
changed={uid(via),*(uid(t) for t,_ in legs)}
wire=make(b,case['start_nm'],case['end_nm'],500000,b.FindNet('+1V8_SYS').GetNetCode(),p.B_Cu)
b.Add(wire)
obs=[o for o in [*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())] if uid(o) not in changed and inflated_box(o,1500000).Contains(via.GetPosition())]
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
shapes=[(l,o.GetEffectiveShape(l)) for o in obs if o.GetNetCode()!=via.GetNetCode() for l in layers if o.IsOnLayer(l)]
holes=[o.GetEffectiveHoleShape() for o in obs if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
land=[o.GetEffectiveShape(o.GetParentFootprint().GetLayer()) for o in obs if isinstance(o,p.PAD)]
rules=[z.Outline() for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
folder=stage/'runs/vdd1-c2303-return'
folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):
    shutil.copy2(src.parent/name,folder/name)
original=p.LoadBoard(str(src))
adopted=None
trials=[]
for _,x,y in sorted((math.hypot(x,y),x,y) for x in range(-16,17) for y in range(-16,17) if 0<math.hypot(x,y)<=16):
    pos=p.VECTOR2I(origin[0]+25000*x,origin[1]+25000*y)
    via.SetPosition(pos)
    drill=via.GetEffectiveHoleShape()
    annulus=via.GetEffectiveShape(p.F_Cu)
    if any(annulus.Collide(s,202000) or drill.Collide(s,252000) for _,s in shapes) or any(drill.Collide(h,252000) or annulus.Collide(h,252000) for h in holes):continue
    if any(annulus.Collide(s,100000) for s in land) or any(annulus.Collide(s,0) for s in rules):continue
    for t,start in legs:
        (t.SetStart if start else t.SetEnd)(pos)
    if any(t.GetEffectiveShape(l).Collide(s,202000) for t,_ in legs for l,s in shapes if l==t.GetLayer()):continue
    out=folder/src.name
    p.ZONE_FILLER(b).Fill(b.Zones())
    p.SaveBoard(str(out),b)
    dr=folder/'drc.json'
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dr),str(out)],capture_output=True,check=True)
    delta=introduced(json.loads((src.parent/'drc.json').read_text()),json.loads(dr.read_text()))
    trials.append(dict(offset_mm=[x*.025,y*.025],delta=delta))
    if delta:continue
    saved=p.LoadBoard(str(out));saved.BuildConnectivity()
    q=saved.FindFootprintByReference('C2303').FindPadByNumber('1')
    ids={uid(o) for o in saved.GetConnectivity().GetConnectedItems(q)}
    if uid(saved.FindFootprintByReference('U2').FindPadByNumber('F1')) not in ids or screen(saved):continue
    guard=verify_preservation(original,saved,replaced_copper=changed)
    adopted=dict(board=str(out.relative_to(stage)),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
                 offset_mm=[x*.025,y*.025],length_mm=case['length_mm'],replaced=sorted(changed),preservation=guard)
    break
(stage/'vdd1-c2303-return.json').write_text(json.dumps(dict(parent_sha256=source['sha256'],candidate=adopted,trials=trials,assembly_ready=False),indent=2)+'\n')
print(bool(adopted),len(trials))
