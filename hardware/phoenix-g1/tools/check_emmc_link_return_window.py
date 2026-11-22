"""Check a C1643 return-barrel pivot against identified VCCQ link corridors."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import pcbnew as p

from pcb_bounds import inflated_box
from pcb_power_leg import make

root = Path(__file__).resolve().parents[1] / 'migration-rk3562/experiments/phy-power-parallel'
stage = json.loads((root / 'layout-memory-n12-neighbors.json').read_text())
screen = json.loads((root / 'emmc-io-link-both-frontiers.json').read_text())
source = root / stage['board']
assert hashlib.sha256(source.read_bytes()).hexdigest() == stage['sha256'] == screen['parent_sha256']
b = p.LoadBoard(str(source))
get_id = lambda item: item.m_Uuid.AsString()
c = b.FindFootprintByReference('C1643').FindPadByNumber('2')
at = tuple(c.GetPosition())
code = c.GetNetCode()
by_uid = {get_id(o): o for o in b.GetTracks()}
rows = []
for candidate in screen['placement_barriers']:
    hits = candidate['hits']
    if len(hits) != 2 or {hit['type'] for hit in hits} != {'PCB_VIA', 'PCB_TRACK'} or any(hit['net'] != 'GND' for hit in hits):
        continue
    via, track = sorted((by_uid[hit['uuid']] for hit in hits), key=lambda o: not isinstance(o, p.PCB_VIA))
    if not c.HitTest(track.GetStart()) and not c.HitTest(track.GetEnd()):
        continue
    old_length = track.GetLength()
    exclude = {get_id(via), get_id(track)}
    neighbours = [o for o in [*b.GetTracks(), *(q for f in b.GetFootprints() for q in f.Pads())] if get_id(o) not in exclude and inflated_box(o,2000000).Contains(c.GetPosition())]
    layers = (p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
    copper = [o.GetEffectiveShape(l) for o in neighbours for l in layers if o.GetNetCode()!=code and o.IsOnLayer(l)]
    rear = [o.GetEffectiveShape(p.B_Cu) for o in neighbours if o.GetNetCode()!=code and o.IsOnLayer(p.B_Cu)]
    lands = [o.GetEffectiveShape(o.GetParentFootprint().GetLayer()) for o in neighbours if isinstance(o,p.PAD)]
    holes = [o.GetEffectiveHoleShape() for o in neighbours if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    cuts = [z.Outline() for z in [*b.Zones(), *(zone for f in b.GetFootprints() for zone in f.Zones())] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    bridge = make(b,*candidate['bridge'],500000,b.FindNet('EMMC_IO_1V8').GetNetCode(),p.B_Cu).GetEffectiveShape(p.B_Cu)
    # Preserve every local fast-signal barrel's nearest grounded stitching-via distance.
    b.BuildConnectivity()
    grounded = {get_id(o) for o in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('U4').FindPadByNumber('69'))}
    stitches = [tuple(o.GetPosition()) for o in b.GetTracks() if isinstance(o,p.PCB_VIA) and get_id(o) in grounded and get_id(o)!=get_id(via)]
    old_at = tuple(via.GetPosition())
    reference=[]
    for o in b.GetTracks():
        if not isinstance(o,p.PCB_VIA) or o.GetNetname()=='GND':continue
        pos=tuple(o.GetPosition())
        if math.dist(pos,old_at)>5000000:continue
        other=min(math.dist(pos,g) for g in stitches)
        if math.dist(pos,old_at)<other:reference.append((o.GetNetname(),pos,math.dist(pos,old_at),other))
    stats = Counter()
    options = []
    for dx in range(-14,15):
        for dy in range(-14,15):
            end = (at[0]+dx*50000,at[1]+dy*50000)
            if math.dist(at,end)>old_length:continue
            check = p.PCB_VIA(b)
            check.SetViaType(via.GetViaType());check.SetLayerPair(p.F_Cu,p.B_Cu)
            check.SetWidth(via.GetWidth(p.F_Cu));check.SetDrill(via.GetDrillValue());check.SetPosition(p.VECTOR2I(*end))
            land = check.GetEffectiveShape(p.F_Cu); hole = check.GetEffectiveHoleShape()
            line = make(b,at,end,track.GetWidth(),code,p.B_Cu).GetEffectiveShape(p.B_Cu)
            if land.Collide(bridge,202000) or line.Collide(bridge,202000):stats['reserved_branch']+=1;continue
            if any(land.Collide(q,52000) for q in lands):stats['solder_opening']+=1;continue
            if any(land.Collide(q,202000) or hole.Collide(q,252000) for q in copper):stats['foreign_copper']+=1;continue
            if any(land.Collide(q,252000) or hole.Collide(q,252000) or line.Collide(q,252000) for q in holes):stats['drill_clearance']+=1;continue
            if any(line.Collide(q,202000) for q in rear) or any(land.Collide(q,0) for q in cuts):stats['return_or_keepout']+=1;continue
            worsened=[net for net,pt,old,other in reference if min(math.dist(pt,end),other)>old+1]
            if worsened:
                stats['reference_distance '+','.join(sorted(set(worsened)))]+=1
                continue
            options.append(end)
    rows.append(dict(bridge=candidate['bridge'],link=candidate['pos'],angle=candidate['angle'],former_return_length_mm=old_length/1e6,available_nm=options,eliminated=stats))
out = dict(parent_sha256=stage['sha256'],ref='C1643.2',records=rows,assembly_ready=False)
(root/'emmc-io-link-return-window.json').write_text(json.dumps(out,indent=2)+'\n')
print([(len(row['available_nm']),row['eliminated']) for row in rows])

# Build a disposable coupon to reroute the rail around a valid return via.
import shutil
import subprocess
from drc_regression import introduced
from pcb_preservation import verify_preservation
from audit_mount_component_reservations import screen as mechanical_screen

folder=root/'runs/emmc-vccq-return-pivot'
folder.mkdir(exist_ok=True)
for name in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):
    shutil.copy2(source.parent/name,folder/name)
winner=None
if rows:
    choices=sorted({tuple(x) for row in rows for x in row['available_nm']},key=lambda x:(math.dist(x,old_at),x))
    for end in choices:
        trial=p.LoadBoard(str(source))
        objects={get_id(t):t for t in trial.GetTracks()}
        shifted,lead=objects[get_id(via)],objects[get_id(track)]
        shifted.SetPosition(p.VECTOR2I(*end))
        if tuple(lead.GetEnd())==old_at:lead.SetEnd(p.VECTOR2I(*end))
        else:
            assert tuple(lead.GetStart())==old_at
            lead.SetStart(p.VECTOR2I(*end))
        path=folder/source.name
        p.ZONE_FILLER(trial).Fill(trial.Zones());p.SaveBoard(str(path),trial)
        subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(path)],check=True,capture_output=True)
        read_drc=lambda directory:json.loads((directory/'drc.json').read_text())
        delta=introduced(read_drc(source.parent),read_drc(folder))
        if delta:continue
        saved=p.LoadBoard(str(path));saved.BuildConnectivity()
        local_ground=saved.FindFootprintByReference('C1643').FindPadByNumber('2')
        members={get_id(t) for t in saved.GetConnectivity().GetConnectedItems(local_ground)}
        if get_id(shifted) not in members or get_id(saved.FindFootprintByReference('U4').FindPadByNumber('69')) not in members or mechanical_screen(saved):continue
        preservation=verify_preservation(b,saved,replaced_copper={get_id(via),get_id(track)})
        winner=dict(board=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),via_nm=end,was_nm=old_at,replaced=[get_id(via),get_id(track)],length_before_mm=old_length/1e6,length_after_mm=lead.GetLength()/1e6,new_drc=delta,preservation=preservation)
        break
out['candidate']=winner
(root/'emmc-io-link-return-window.json').write_text(json.dumps(out,indent=2)+'\n')
print('Reloaded',bool(winner))
