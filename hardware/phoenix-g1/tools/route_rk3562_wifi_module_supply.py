#!/usr/bin/env python3
"""Candidate ferrite-to-module supply and bypass; not current or thermal signoff."""
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
ap.add_argument('--auto-bounds',action='store_true')
args = ap.parse_args()
assert args.input.resolve() != args.output.resolve()
b = p.LoadBoard(str(args.input)); b.BuildConnectivity()
pads = {(f.GetReference(), a.GetNumber()): a for f in b.GetFootprints() for a in f.Pads()}
name = 'WIFI_VBAT'; code = b.FindNet(name).GetNetCode()
bounds=(40,16,60,39)
if args.auto_bounds:
 anchors=[pads[k].GetPosition() for k in [('FB2001','2'),('U25','9'),('C2001','1'),('C2002','1')]];xs=[p.ToMM(q.x) for q in anchors];ys=[p.ToMM(q.y) for q in anchors]
 bounds=(max(1,min(xs)-5),max(1,min(ys)-5),min(89,max(xs)+5),min(39,max(ys)+5))
outer = LocalRouter(b, bounds, width=.5, grid=.05)
inner = LocalRouter(b, bounds, width=1.0, grid=.05)
front = outer.blocked(p.F_Cu, name)
middle = inner.blocked(p.In3_Cu, name)
via_blocked = set()
for layer in (p.F_Cu, p.In1_Cu, p.In2_Cu, p.In3_Cu, p.In4_Cu, p.B_Cu):
    via_blocked |= outer.blocked(layer, name, .6, True)


def pairs(pad, preferred):
    front = outer.blocked(p.B_Cu if pad.IsOnLayer(p.B_Cu) else p.F_Cu, name)
    start = outer.cell(outer.xy(pad))
    candidates = []
    extent=200 if args.auto_bounds else 120
    for dx in range(-extent, extent+1, 2):
        for dy in range(-extent, extent+1, 2):
            q = (start[0]+dx, start[1]+dy)
            if outer.within(q) and q not in via_blocked and q not in middle and q not in front:
                candidates.append(q)
    candidates.sort(key=lambda q: math.dist(outer.world(q), preferred))
    accessible = []
    for q in candidates[:2400 if args.auto_bounds else 600]:
        path = outer.solve(front, start, q)
        if path and sum(math.dist(a, z) for a, z in zip(path, path[1:])) <= 10:
            accessible.append((q, [outer.xy(pad)]+path))
            if len(accessible) == 100:
                break
    print('Endpoint', pad.GetParentFootprint().GetReference(), 'start blocked', start in front, 'safe sites', len(candidates), 'accessible', len(accessible), flush=True)
    result = []
    for i, (a, pa) in enumerate(accessible):
        for z, pz in accessible[i+1:]:
            spacing = math.dist(outer.world(a), outer.world(z))
            if .65 <= spacing <= 2.0:
                bridge = inner.solve(middle, a, z)
                if bridge:
                    result.append((a, z, pa, pz, bridge))
    return result


starts = pairs(pads['FB2001', '2'], (54, 21))
module_xy=outer.xy(pads['U25','9'])
goals = pairs(pads['U25', '9'], (module_xy[0]+1,module_xy[1]+1) if args.auto_bounds else (51.7,22.7))
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
assert choice, 'No candidate 1.0 mm inner-layer feed'


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
added_vias = set()
for pair, layer in ((a, p.F_Cu), (z, p.B_Cu)):
    for q, stub in zip(pair[:2], pair[2:4]):
        length = add(stub, .5, layer)
        v = p.PCB_VIA(b); v.SetPosition(point(outer.world(q)))
        v.SetWidth(p.FromMM(.6)); v.SetDrill(p.FromMM(.3))
        v.SetViaType(p.VIATYPE_THROUGH); v.SetLayerPair(p.F_Cu, p.B_Cu); v.SetNetCode(code)
        if q not in added_vias:
            b.Add(v); added_vias.add(q)
        fanouts.append({'via_xy_mm': outer.world(q), 'outer_stub_length_mm': round(length, 4)})
    add(pair[4], 1.0, p.In3_Cu)
length = add(path, 1.0, p.In3_Cu)
# Local bypass branches use their actual component side.
for ref, anchor, layer, width in [('C2001', ('FB2001', '2'), p.F_Cu, .8),
                                  ('C2002', ('U25', '9'), p.B_Cu, .4)]:
    router = LocalRouter(b, bounds if args.auto_bounds else (49, 18, 59, 27), width=width)
    a, z = pads[ref, '1'], pads[anchor]
    path = router.solve(router.blocked(layer, name), router.cell(router.xy(a)), router.cell(router.xy(z)))
    assert path, 'No bypass supply path '+ref
    add([router.xy(a)]+path+[router.xy(z)], width, layer)
# Ground returns: explicit same-side copper into through vias, then filled planes.
code = b.FindNet('GND').GetNetCode()
for ref, layer in [('C2001', p.F_Cu), ('C2002', p.B_Cu)]:
    router = LocalRouter(b, bounds if args.auto_bounds else (49, 18, 60, 28), width=.4)
    pad = pads[ref, '2']
    if args.auto_bounds and b.GetConnectivity().GetConnectedTracks(pad):continue
    start = router.cell(router.xy(pad))
    blocked = router.blocked(layer, 'GND')
    forbidden = set()
    for ly in (p.F_Cu, p.In1_Cu, p.In2_Cu, p.In3_Cu, p.In4_Cu, p.B_Cu):
        forbidden |= router.blocked(ly, 'GND', .6, True)
    options = [(start[0]+dx,start[1]+dy) for dx in range(-60,61,2) for dy in range(-60,61,2)]
    choice = None
    for q in sorted(options, key=lambda q: math.dist(q,start)):
        if q in forbidden or not router.within(q): continue
        path = router.solve(blocked, start, q)
        if path:
            choice = q,path; break
    assert choice, 'No bypass ground return '+ref
    q,path=choice; add([router.xy(pad)]+path, .4, layer)
    v=p.PCB_VIA(b);v.SetPosition(point(router.world(q)));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3))
    v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(code);b.Add(v)

p.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
reached = {i.m_Uuid.AsString() for i in b.GetConnectivity().GetConnectedItems(pads['FB2001', '2'])}
assert pads['U25', '9'].m_Uuid.AsString() in reached
p.SaveBoard(str(args.output), b)
report = {'status': 'CANDIDATE WIFI MODULE FEED; DRC AND CURRENT QUALIFICATION REQUIRED',
          'pcb_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
          'net': name, 'trunk_layer': 'In3.Cu', 'trunk_width_mm': 1.0,
          'trunk_length_mm': round(length, 4), 'via_land_drill_mm': [.6, .3],
          'outer_stub_width_mm': .5, 'endpoint_vias': fanouts,
          'limitations': ['Module supply only; internal buck, VDDIO, sequencing and RF remain unqualified.',
                          'Narrow IC necks, copper thickness, current sharing, via fill and temperature are not qualified.',
                          'No electrical simulation or hardware test.'], 'production_ready': False}
args.report.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
