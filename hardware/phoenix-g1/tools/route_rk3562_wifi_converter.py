#!/usr/bin/env python3
"""Local U26 power copper candidate, requiring independent DRC and continuity.

Run with KiCad Python on the converter placement candidate. No main 5 V
distribution, module output feed, PI, thermal or stability qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import pcbnew as p

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--input', required=True, type=Path)
ap.add_argument('--output', required=True, type=Path)
ap.add_argument('--report', required=True, type=Path)
args = ap.parse_args()
assert args.input.resolve() != args.output.resolve()
b = p.LoadBoard(str(args.input))
fps = {f.GetReference(): f for f in b.GetFootprints()}
pads = {(r, a.GetNumber()): a for r, f in fps.items() for a in f.Pads()}

def point(q):
    return p.VECTOR2I(p.FromMM(q[0]), p.FromMM(q[1]))

def xy(ref, pin):
    a = pads[ref, str(pin)]
    return (p.ToMM(a.GetPosition().x), p.ToMM(a.GetPosition().y))

def net(ref, pin):
    return pads[ref, str(pin)].GetNetCode()

def tracks(name, width, points, layer=p.F_Cu):
    code = b.FindNet(name).GetNetCode()
    for a, z in zip(points, points[1:]):
        if a == z:
            continue
        t = p.PCB_TRACK(b)
        t.SetStart(point(a)); t.SetEnd(point(z))
        t.SetWidth(p.FromMM(width)); t.SetLayer(layer); t.SetNetCode(code)
        b.Add(t)

def via(name, q, land=.45, drill=.2):
    v = p.PCB_VIA(b)
    v.SetPosition(point(q)); v.SetWidth(p.FromMM(land)); v.SetDrill(p.FromMM(drill))
    v.SetViaType(p.VIATYPE_THROUGH); v.SetLayerPair(p.F_Cu, p.B_Cu)
    v.SetNetCode(b.FindNet(name).GetNetCode()); b.Add(v)

# Refuse a placement different from the coordinates reviewed for these routes.
assert xy('U26', 17) == (50.5, 33.0)
assert all(not b.GetConnectivity().GetConnectedTracks(a) for a in fps['U26'].Pads())
before_tracks = len(list(b.GetTracks()))

# Short switch-node bus and a wider single-layer branch to the inductor.
for pin in (1, 2, 3):
    q = xy('U26', pin)
    tracks('WIFI_VBAT_SW', .25, [q, (48.6, q[1])])
tracks('WIFI_VBAT_SW', .3, [(48.6, 32.25), (48.6, 33.25)])
tracks('WIFI_VBAT_SW', 1.0, [(48.6, 32.75), (47.6, 33.75), (47.6, 35.05), xy('L2201', 1)])
tracks('+3V58_WIFI', 1.0, [xy('L2201', 2), (45.5, 30), (47, 28.5), xy('C2204', 1)])

# PVIN/AVIN local bus; the main distribution from U15 remains separate work.
for pin in (10, 11, 12):
    q = xy('U26', pin)
    tracks('+5V_MAIN', .25, [q, (52.5, q[1])])
tracks('+5V_MAIN', .35, [(52.5, 32.25), (52.5, 33.25)])
tracks('+5V_MAIN', .8, [xy('C2201', 1), (52.5, 31.95), (52.5, 32.75)])
tracks('+5V_MAIN', .25, [xy('C2202', 1), (53, 33.52), (52.5, 33.25)])
tracks('+5V_MAIN', .2, [xy('U26', 13), (51.25, 31.1), (52.2, 31.1), (52.5, 31.4), (52.5, 31.95)])

# AGND and PGND connect directly to the exposed pad on the front copper.
for pin in (6, 7):
    q = xy('U26', pin)
    tracks('GND', .25, [q, (q[0], 33.5)])
for pin in (15,):
    q = xy('U26', pin)
    tracks('GND', .25, [q, (q[0], 32.5)])
tracks('GND', .2, [xy('U26', 16), (50, 31.85), (50, 32.5)])
tracks('GND', .2, [xy('U26', 8), (51, 34.15), (51, 33.5)])
tracks('GND', .25, [xy('U26', 15), xy('U26', 16)])
tracks('GND', .8, [xy('C2201', 2), (53.5, 29.8), (49.75, 29.8)])
tracks('GND', .5, [xy('C2204', 2), (49.75, 28.5), (49.75, 31.1)])
tracks('GND', .25, [(49.75, 31.1), xy('U26', 16)])
# Candidate filled/plugged thermal vias: process remains unqualified.
for q in [(50.15, 32.65), (50.85, 32.65), (50.15, 33.35)]:
    via('GND', q)

tracks('WIFI_VBAT_SS', .2, [xy('U26', 9), (52.02, 34.0), xy('C2203', 1)])
tracks('WIFI_VBAT_FB', .2, [xy('U26', 5), (49.75, 36.2), xy('R2203', 1)])
tracks('WIFI_VBAT_FB', .2, [xy('R2203', 1), (49.5, 37.25), xy('R2202', 2)])

from local_pcb_router import LocalRouter
router = LocalRouter(b, (40, 27.5, 56, 39))
for ar, ap, zr, zp in [('U26', '14', 'C2204', '1'), ('R2202', '1', 'C2204', '1'), ('R2201', '2', 'C2204', '1'), ('U26', '4', 'R2201', '1')]:
    router.back_pair(pads[ar, ap], pads[zr, zp], tracks, via)
# Power-good enables the system 3.3 V regulator; this is a logic-current path.
sequence_router = LocalRouter(b, (10, 27, 56, 39))
sequence_router.back_pair(pads['U17', '13'], pads['R2201', '1'], tracks, via)
for ref in ['C2202', 'C2203', 'R2203']:
    router.ground_escape(pads[ref, '2'], tracks, via)
p.ZONE_FILLER(b).Fill(b.Zones())
b.BuildConnectivity()
p.SaveBoard(str(args.output), b)
report = {
    'status': 'LOCAL POWER COPPER CANDIDATE; DRC/CONTINUITY REQUIRED',
    'pcb_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
    'added_track_and_via_items': len(list(b.GetTracks()))-before_tracks,
    'source': 'https://www.ti.com/lit/ds/symlink/tps62130.pdf, sections 11.1/11.2',
    'limitations': ['Not a completed converter or power distribution.',
                    'No impedance, current, thermal or loop stability qualification.',
                    'Thermal via fill/plug and paste process not approved.'],
    'production_ready': False,
}
args.report.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
