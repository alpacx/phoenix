"""Evaluate drill, annulus and assembly clearances for the finite-width return paths."""
import itertools
import json
import math
import os
from pathlib import Path
import sys
import pcbnew as pcb
from pcb_bounds import inflated_box
from pcb_power_leg import barrel,ls
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((root/'rotated-buck-return-zone.json').read_text())
board=pcb.LoadBoard(str(root/base['board']));code=board.FindNet('GND').GetNetCode()
sites=json.loads(Path(sys.argv[1]).read_text())
probe=barrel(board,(0,0),code)
zref=[z.GetFilledPolysList(pcb.In4_Cu) for z in board.Zones() if z.GetNetname()=='GND' and z.IsOnLayer(pcb.In4_Cu) and not z.GetIsRuleArea()]
rules=[z.Outline() for z in [*list(board.Zones()),*(z for f in board.GetFootprints() for z in f.Zones())] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
edges=[o.GetEffectiveShape(pcb.Edge_Cuts) for o in list(board.GetDrawings())+[g for f in board.GetFootprints() for g in f.GraphicalItems()] if o.IsOnLayer(pcb.Edge_Cuts)]
geos={}
singletons={}
positions={}
for key,rows in sites.items():
    fp=board.FindFootprintByReference(key);at=fp.FindPadByNumber('2').GetPosition()
    pads=[q for f in board.GetFootprints() for q in f.Pads() if inflated_box(q,3300000).Contains(at)]
    copper=pads+[t for t in board.GetTracks() if inflated_box(t,3300000).Contains(at)]
    holes=[(o.GetNetCode(),o.GetEffectiveHoleShape()) for o in copper if isinstance(o,pcb.PCB_VIA) or isinstance(o,pcb.PAD) and o.GetDrillSize().x]
    lands=[(o,o.GetEffectiveShape(o.GetParentFootprint().GetLayer())) for o in pads]
    shapes=[(o,o.GetEffectiveShape(l)) for o in copper if o.GetNetCode()!=code for l in ls if o.IsOnLayer(l)]
    legal=[];counts={};relief={}
    for x,y,distance in rows:
        xy=round(x*1e6),round(y*1e6)
        if xy in geos:
            reason=geos[xy]
        else:
            pt=pcb.VECTOR2I(*xy);probe.SetPosition(pt);land=probe.GetEffectiveShape(pcb.F_Cu);drill=probe.GetEffectiveHoleShape()
            if not any(z.Contains(pt) for z in zref):reason='no adjacent filled reference'
            elif any(land.Collide(sh,50000) for _,sh in lands):reason='component land'
            elif any(drill.Collide(sh,252000) or net!=code and land.Collide(sh,252000) for net,sh in holes):reason='existing drill'
            elif any(land.Collide(sh,202000) or drill.Collide(sh,252000) for _,sh in shapes):reason='foreign copper'
            elif any(land.Collide(sh,252000) for sh in edges):reason='board edge'
            elif any(land.Collide(sh,0) for sh in rules):reason='via keepout'
            else:reason='clear'
            geos[xy]=reason
            if reason in ('component land','foreign copper') and not any(drill.Collide(sh,252000) or net!=code and land.Collide(sh,252000) for net,sh in holes) and not any(land.Collide(sh,252000) for sh in edges) and not any(land.Collide(sh,0) for sh in rules):
                conflicts={o.m_Uuid.AsString():o for o,sh in lands if land.Collide(sh,50000)}
                for o,sh in shapes:
                    if o.m_Uuid.AsString() in conflicts:continue
                    if land.Collide(sh,202000) or drill.Collide(sh,252000):conflicts[o.m_Uuid.AsString()]=o
                    if len(conflicts)>1:break
                if len(conflicts)==1:
                    obj=next(iter(conflicts.values()))
                    if isinstance(obj,pcb.PAD):singletons[xy]=obj.GetParentFootprint().GetReference()+'.'+obj.GetNumber()
        if xy in singletons:
            label=singletons[xy];relief.setdefault(label,[]).append([*xy,distance])
        counts[reason]=counts.get(reason,0)+1
        if reason=='clear':legal.append([*xy,distance])
    positions[key]=dict(legal=sorted(legal,key=lambda row:row[2]),counts=counts,single_land_relief={k:sorted(v,key=lambda x:x[2]) for k,v in relief.items()})
out=dict(board_sha256=base['sha256'],candidate_centres=positions,assembly_ready=False)
(root/'rotated-buck-plane-barrel-screen.json').write_text(json.dumps(out,indent=2)+'\n')
print([(k,len(v['legal'])) for k,v in positions.items()],flush=True);os._exit(0)
