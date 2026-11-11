#!/usr/bin/env python3
"""Candidate 5 V feed from U15 to U26; not full-board distribution or ampacity signoff."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import pcbnew as p
from local_pcb_router import LocalRouter

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--input', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
ap.add_argument('--report', type=Path, required=True)
args = ap.parse_args()
assert args.input.resolve() != args.output.resolve()
b = p.LoadBoard(str(args.input)); b.BuildConnectivity()
pads = {(f.GetReference(), a.GetNumber()): a for f in b.GetFootprints() for a in f.Pads()}
name = '+5V_MAIN'; code = b.FindNet(name).GetNetCode()
outer = LocalRouter(b, (1, 27, 56, 39), width=.5, grid=.05)
inner = LocalRouter(b, (1, 27, 56, 39), width=1.5, grid=.05)
front = outer.blocked(p.F_Cu, name)
middle = inner.blocked(p.In3_Cu, name)
via_blocked = set()
for layer in (p.F_Cu, p.In1_Cu, p.In2_Cu, p.In3_Cu, p.In4_Cu, p.B_Cu):
    via_blocked |= outer.blocked(layer, name, .6, True)


def pairs(pad, preferred):
    start = outer.cell(outer.xy(pad))
    candidates = []
    for dx in range(-120, 121, 4):
        for dy in range(-120, 121, 4):
            q = (start[0]+dx, start[1]+dy)
            if outer.within(q) and q not in via_blocked and q not in middle and q not in front:
                candidates.append(q)
    candidates.sort(key=lambda q: math.dist(outer.world(q), preferred))
    accessible = []
    for q in candidates[:600]:
        path = outer.solve(front, start, q)
        if path and sum(math.dist(a, z) for a, z in zip(path, path[1:])) <= 8:
            accessible.append((q, [outer.xy(pad)]+path))
            if len(accessible) == 30:
                break
    print('Endpoint', pad.GetParentFootprint().GetReference(), 'start blocked', start in front, 'safe sites', len(candidates), 'accessible', len(accessible), flush=True)
    result = []
    for i, (a, pa) in enumerate(accessible):
        for z, pz in accessible[i+1:]:
            spacing = math.dist(outer.world(a), outer.world(z))
            if .65 <= spacing <= 1.1:
                bridge = inner.solve(middle, a, z)
                if bridge:
                    result.append((a, z, pa, pz, bridge))
    return result


source_sites=[(7.9,33.8),(8.6,34.4)]
assert all(any(isinstance(t,p.PCB_VIA) and t.GetNetname()==name and math.dist(outer.xy(t),q)<.001 for t in b.GetTracks()) for q in source_sites), 'Main output fanout must be reserved by USB routing first'
starts=[(outer.cell(source_sites[0]),outer.cell(source_sites[1]),[],[],source_sites)]
goals = pairs(pads['C2201', '1'], (53.4, 32.4))
assert starts and goals, f'No paired supply via sites: {len(starts)} / {len(goals)}'
choice = None
for a in starts[:60]:
    for z in goals[:60]:
        path = inner.solve(middle, a[0], z[0])
        if path:
            choice = a, z, path
            break
    if choice:
        break
assert choice, 'No candidate 1.5 mm inner-layer feed'


def point(q):
    return p.VECTOR2I(p.FromMM(q[0]), p.FromMM(q[1]))


def add(points, width, layer):
    total = 0
    for a, z in zip(points, points[1:]):
        if math.dist(a, z) < .00001:
            continue
        t = p.PCB_TRACK(b); t.SetStart(point(a)); t.SetEnd(point(z))
        t.SetLayer(layer); t.SetWidth(p.FromMM(width)); t.SetNetCode(code); b.Add(t)
        total += math.dist(a, z)
    return total


a, z, path = choice
fanouts = []
for pair in (z,):
    for q, stub in zip(pair[:2], pair[2:4]):
        length = add(stub, .5, p.F_Cu)
        v = p.PCB_VIA(b); v.SetPosition(point(outer.world(q)))
        v.SetWidth(p.FromMM(.6)); v.SetDrill(p.FromMM(.3))
        v.SetViaType(p.VIATYPE_THROUGH); v.SetLayerPair(p.F_Cu, p.B_Cu); v.SetNetCode(code); b.Add(v)
        fanouts.append({'via_xy_mm': outer.world(q), 'outer_stub_length_mm': round(length, 4)})
    add(pair[4], 1.5, p.In3_Cu)
length = add(path, 1.5, p.In3_Cu)
p.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
reached = {i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(pads['U15', '5'])}
assert all(pads['U26', str(pin)].m_Uuid.AsString() in reached for pin in (10, 11, 12, 13))
p.SaveBoard(str(args.output), b)
report = {'status': 'CANDIDATE WIFI INPUT FEED; DRC AND CURRENT QUALIFICATION REQUIRED',
          'pcb_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
          'net': name, 'trunk_layer': 'In3.Cu', 'trunk_width_mm': 1.5,
          'trunk_length_mm': round(length, 4), 'via_land_drill_mm': [.6, .3],
          'outer_stub_width_mm': .5, 'target_vias': fanouts, 'reserved_source_vias_xy_mm': source_sites,
          'limitations': ['Only U15-to-U26 feed; other +5V_MAIN loads are not connected by this step.',
                          'Narrow IC necks, copper thickness, current sharing, via fill and temperature are not qualified.',
                          'No electrical simulation or hardware test.'], 'production_ready': False}
args.report.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
