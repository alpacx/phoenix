"""Find complete rings of eight foreign BGA lands and bound their available surface exits."""
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import pcbnew as p

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
meta=json.loads((root/'layout-soc-tx-series.json').read_text());path=root/meta['board']
assert hashlib.sha256(path.read_bytes()).hexdigest()==meta['sha256']
board=p.LoadBoard(str(path));board.BuildConnectivity()
rules=json.loads(path.with_suffix('.kicad_pro').read_text())['board']['design_settings']['rules']
assert rules['min_via_diameter']==.45 and rules['min_through_hole_diameter']==.2 and rules['min_hole_clearance']==.25
dru=path.with_suffix('.kicad_dru').read_text()
assert 'Experimental CPU land spacing' in dru and '0.0762mm' in dru
soc=board.FindFootprintByReference('U1')
pads={tuple(a.GetPosition()):a for a in soc.Pads()}
pitch=.5
directions=[(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1)]
link_clearance=.0762
excluded={'GND','+3V3_IO','+1V8_SYS','+3V3_SYS','PMIC_SW5','+5V_ADDON','PHY_XIN','PHY_XOUT'}
records=[]
for center,pad in sorted(pads.items()):
    net=pad.GetNetname()
    if not net or net not in meta['open_nets'] or net.startswith(('EXP_','LPDDR4_')) or net in excluded:continue
    if pad.GetShape()!=p.PAD_SHAPE_CIRCLE or pad.GetSize().x!=250000 or pad.GetSize().y!=250000:continue
    if len(board.GetConnectivity().GetConnectedItems(pad))>1:continue
    ring=[pads.get((center[0]+x*500000,center[1]+y*500000)) for x,y in directions]
    if any(q is None or q.GetShape()!=p.PAD_SHAPE_CIRCLE or q.GetSize().x!=250000 or q.GetSize().y!=250000 or q.GetNetCode()==pad.GetNetCode() for q in ring):continue
    # An unassigned ball is still a physical copper land.
    expanded_radius=.125+.2/2+link_clearance
    assert 2*expanded_radius>pitch # consecutive forbidden disks overlap
    min_offset_no_solder_land_overlap=.125+rules['min_via_diameter']/2
    # In any octant of the enclosing square use the nearest cardinal/diagonal ring ball.
    a=pitch-min_offset_no_solder_land_overlap/math.sqrt(2)
    upper_bound=math.hypot(a,pitch/2)
    needed=.125+rules['min_through_hole_diameter']/2+rules['min_hole_clearance']
    assert upper_bound<needed
    records.append(dict(pin=pad.GetNumber(),net=net,ring=[(q.GetNumber(),q.GetNetname()) for q in ring]))
report=dict(board_sha256=meta['sha256'],footprint='U1',pitch_mm=pitch,pad_diameter_mm=.25,track_width_mm=.2,
            local_copper_clearance_mm=link_clearance,consecutive_exclusion_disk_overlap_mm=round(2*expanded_radius-pitch,4),
            through_via_minimum_mm=[.45,.2],nonoverlap_center_offset_mm=min_offset_no_solder_land_overlap,
            upper_bound_distance_from_off_land_barrel_to_nearest_foreign_center_mm=upper_bound,
            required_drill_center_to_foreign_land_center_mm=needed,closed_singletons=records,
            restriction='Current straight/curved surface tracks and off-land through vias. A larger plated and capped solder land, blind/stacked microvias, or a manufacturing process change needs separate review.',
            limitations='Only exact 0.5-mm rings with eight foreign 0.25-mm round lands and isolated non-DDR pads. Counts are a lower bound. No assembly, SI, or thermal claim.')
(root/'bga-closed-escape-rings.json').write_text(json.dumps(report,indent=2)+'\n')
print(len(records),sorted({r['net'] for r in records}),flush=True);os._exit(0)
