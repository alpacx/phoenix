#!/usr/bin/env python3
"""Measure the verified board against a 90x30 target without modifying CAD.

Bounding boxes include pads/body graphics but exclude reference/value text.
This is a relocation inventory, not a packing or routing feasibility proof.
Run with KiCad's bundled Python (pcbnew).
"""
import hashlib
import html
import json
from pathlib import Path
import pcbnew as p

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'migration-rk3562/experiments/lpddr4-1gb'
OUT = BASE / 'compact-90x30'


def bounds(item):
    r = item.GetBoundingBox(False, False) if isinstance(item, p.FOOTPRINT) else item.GetBoundingBox()
    return [round(p.ToMM(v), 4) for v in (r.GetX(), r.GetY(), r.GetRight(), r.GetBottom())]


def inside(box, y, margin=0.5):
    return box[0] >= margin and box[2] <= 90-margin and box[1] >= y+margin and box[3] <= y+30-margin


def main():
    checkpoint = json.loads((BASE / 'working-board.json').read_text())
    source = BASE / checkpoint['board']
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == checkpoint['sha256'], 'Checkpoint hash mismatch'
    board = p.LoadBoard(str(source))
    board.BuildConnectivity()
    connectivity = board.GetConnectivity()
    rows = []
    for f in board.GetFootprints():
        rows.append({'ref': f.GetReference(), 'value': f.GetValue(), 'side': f.GetLayerName(),
                     'bbox_mm': bounds(f),
                     'has_connected_tracks': any(connectivity.GetConnectedTracks(a) for a in f.Pads())})
    # Connector protrusions need a separate mechanical review, not silent exclusion.
    options = []
    for step in range(21):
        y = step / 2
        outside = [r for r in rows if not inside(r['bbox_mm'], y)]
        options.append({'origin_y_mm': y, 'outside_count': len(outside),
                        'routed_outside_count': sum(r['has_connected_tracks'] for r in outside)})
    options.sort(key=lambda x: (x['routed_outside_count'], x['outside_count'], x['origin_y_mm']))
    y = options[0]['origin_y_mm']
    outside = [r for r in rows if not inside(r['bbox_mm'], y)]
    copper = [t for t in board.GetTracks() if not inside(bounds(t), y)]
    report = {'status': 'MECHANICAL_SCREEN_ONLY_NOT_A_ROUTED_CANDIDATE',
              'source': str(source.relative_to(ROOT)), 'source_sha256': digest,
              'target_pcb_mm': [90, 30], 'edge_guard_mm': .5, 'selected_window_y_mm': y,
              'footprint_count': len(rows), 'windows': options,
              'relocation_or_edge_review': outside,
              'track_or_via_boxes_outside_guard': len(copper),
              'critical_components': [r for r in rows if r['ref'] in ('U1','U2','U18','U25','J1','J2','J3')],
              'additional_reservations_not_in_existing_board': [
                  'eMMC package, bypass and routing replacing SPI NOR; shared SoC pins prohibit parallel population',
                  'Display attachment and board-mounted five-way control',
                  'Polarized expansion connector, USB host, protected power and mechanical supports',
                  'Passive heat path and LTE accessory antenna/height envelope'],
              'not_verified': ['Component height and enclosure fit', 'Courtyard placement after relocation',
                               'DDR/USB/RF routing and impedance', 'Power integrity and thermal behavior'],
              'assembly_ready': False}
    OUT.mkdir(exist_ok=True)
    (OUT / 'placement-screen.json').write_text(json.dumps(report, indent=2)+'\n')
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="-4 -9 98 108">',
           '<rect x="-4" y="-9" width="98" height="108" fill="white"/>']
    for side, offset in [('F.Cu', 0), ('B.Cu', 52)]:
        svg.append(f'<g transform="translate(0 {offset})"><text y="-5" font-size="2.6">{side}: 90 x 30 mm target over existing 90 x 40 PCB</text>')
        svg.append('<rect width="90" height="40" fill="#f1f5f9" stroke="#64748b" stroke-width="0.2"/>')
        svg.append(f'<rect y="{y}" width="90" height="30" fill="none" stroke="#15803d" stroke-width="0.5"/>')
        for r in rows:
            if r['side'] != side:
                continue
            x1,y1,x2,y2 = r['bbox_mm']
            color = '#dc2626' if not inside(r['bbox_mm'], y) else '#2563eb'
            svg.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" fill="{color}" fill-opacity="0.17" stroke="{color}" stroke-width="0.1"><title>{html.escape(r["ref"]+": "+r["value"])}</title></rect>')
            if r['ref'].startswith(('U','J')):
                svg.append(f'<text x="{x1}" y="{y1+1.5}" font-size="1.5">{r["ref"]}</text>')
        svg.append('</g>')
    svg.append('<text y="97" font-size="2">Red: relocation/edge review. No feasibility or production approval.</text></svg>')
    (OUT / 'placement-screen.svg').write_text(''.join(svg))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    print(json.dumps({k: report[k] for k in ('selected_window_y_mm','footprint_count','track_or_via_boxes_outside_guard')}))
    print(json.dumps(options[0]))


if __name__ == '__main__':
    main()
