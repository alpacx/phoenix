#!/usr/bin/env python3
"""EXPERIMENTAL, NOT INTEGRATED. Place the AP6256 VDDIO bypass capacitors as a local group; work on an explicit candidate PCB.

This does not approve the circuit, thermal design or fabrication process.
Run with KiCad Python. Never move a footprint with already connected tracks.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import pcbnew as p

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--input', required=True, type=Path)
ap.add_argument('--output', required=True, type=Path)
ap.add_argument('--report', required=True, type=Path)
args = ap.parse_args()
assert args.input.resolve() != args.output.resolve(), 'Use a separate candidate file'
b = p.LoadBoard(str(args.input))
b.BuildConnectivity()
conn = b.GetConnectivity()
fps = {f.GetReference(): f for f in b.GetFootprints()}

def point(x, y):
    return p.VECTOR2I(p.FromMM(x), p.FromMM(y))

def position(f):
    return dict(x=p.ToMM(f.GetPosition().x), y=p.ToMM(f.GetPosition().y),
                orientation=f.GetOrientationDegrees(), side='back' if f.IsFlipped() else 'front')

def box(f):
    q = f.GetBoundingBox(False, False)
    return [p.ToMM(q.GetX())+.025, p.ToMM(q.GetY())+.025,
            p.ToMM(q.GetRight())-.025, p.ToMM(q.GetBottom())-.025]

def overlap(a, z):
    return a[0] < z[2] and a[2] > z[0] and a[1] < z[3] and a[3] > z[1]

def movable(f):
    return not any(conn.GetConnectedTracks(a) for a in f.Pads()) and not any(
        a.GetDrillSize().x for a in f.Pads())

before = {r: position(f) for r, f in fps.items()}
group = {'C2006': (37.25,25.5,180), 'C2005': (37.25,23.75,180), 'C2004': (37.25,22,180)}
for ref, (x, y, angle) in group.items():
    f = fps[ref]
    assert movable(f), f'{ref} already routed or drilled'
    if not f.IsFlipped():
        f.Flip(f.GetPosition(), False)
    f.SetOrientationDegrees(angle)
    f.SetPosition(point(x, y))

for r, f in fps.items():
    if r not in group:
        continue
    assert all(not overlap(box(f), box(fps[z])) for z in group if z != r), r

displaced = []
for r, f in fps.items():
    if r not in group and f.IsFlipped() and any(overlap(box(f), box(fps[z])) for z in group):
        assert r.startswith('C'), f'Cannot displace functional block {r}'
        assert movable(f), f'Cannot move routed component {r}'
        displaced.append(r)

occupied = {False: [], True: [(36.1,21.2,38.4,26.3)]}
for r, f in fps.items():
    if r not in displaced:
        occupied[f.IsFlipped()].append(box(f))
        if any(a.GetDrillSize().x for a in f.Pads()):
            occupied[not f.IsFlipped()].append(box(f))

for r in sorted(displaced, key=lambda r: -(box(fps[r])[2]-box(fps[r])[0])*(box(fps[r])[3]-box(fps[r])[1])):
    f = fps[r]
    original = before[r]
    sites = sorted(((x/4, y/4) for x in range(122, 251) for y in range(8, 153)),
                   key=lambda xy: math.dist(xy, (original['x'], original['y'])))
    for x, y in sites:
        f.SetPosition(point(x, y))
        q = box(f)
        if q[0] < 1 or q[1] < 1 or q[2] > 89 or q[3] > 39:
            continue
        if not any(overlap(q, z) for z in occupied[True]):
            occupied[True].append(q)
            break
    else:
        raise RuntimeError(f'No nearby collision-free site for {r}')

p.ZONE_FILLER(b).Fill(b.Zones())
p.SaveBoard(str(args.output), b)
changes = {r: {'before': before[r], 'after': position(f)} for r, f in fps.items() if before[r] != position(f)}
report = {
    'status': 'LOCAL VDDIO PLACEMENT CANDIDATE; DRC AND ROUTING REQUIRED',
    'source': 'Existing AP6256 circuit: reference/wifi-ap6256.pdf and ROCK 3C sheet22; electrical layout qualification remains open',
    'input_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
    'output_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
    'changes': changes, 'group': sorted(group), 'displaced_unrouted_refs': sorted(displaced),
    'limitations': ['Placement only, not loop inductance or stability qualification.',
                    'Displaced unrouted components still require their own local layout review.',
                    'No MPN, schematic net or component value has changed.'],
    'production_ready': False,
}
args.report.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
