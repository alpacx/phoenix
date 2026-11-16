#!/usr/bin/env python3
"""Inventory real display pads and copper against schematic contracts; not a release approval."""
import hashlib
import json
from pathlib import Path
import pcbnew as p

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'migration-rk3562/experiments/pmic-ldo-inputs'
REVIEW = ROOT / 'migration-rk3562/experiments/emmc-system/system/review'
checkpoint = json.loads((D / 'working-candidate.json').read_text())
source = D / checkpoint['board']
assert hashlib.sha256(source.read_bytes()).hexdigest() == checkpoint['sha256']
board = p.LoadBoard(str(source))
board.BuildConnectivity()
pads = {(f.GetReference(), q.GetNumber()): q for f in board.GetFootprints() for q in f.Pads()}
expected = {}
for name in ('display-power-expected.json', 'display-signals-expected.json'):
    for row in json.loads((REVIEW / name).read_text()):
        key = (row['ref'], row['pin'])
        if key in expected:
            assert expected[key]['net'] == row['net'], key
        expected[key] = row
missing, mismatches, nets = [], [], {}
for key, row in expected.items():
    if key not in pads:
        missing.append(row)
        continue
    pad = pads[key]
    if pad.GetNetname() != (row['net'] or ''):
        mismatches.append({'pad': '.'.join(key), 'expected': row['net'], 'actual': pad.GetNetname()})
    if row['net']:
        nets.setdefault(row['net'], []).append(key)
groups = {}
for name, keys in nets.items():
    remaining = set(keys)
    clusters = []
    while remaining:
        first = min(remaining)
        connected = {q.m_Uuid.AsString() for q in board.GetConnectivity().GetConnectedItems(pads[first])}
        connected.add(pads[first].m_Uuid.AsString())
        cluster = sorted(key for key in remaining if pads[key].m_Uuid.AsString() in connected)
        remaining.difference_update(cluster)
        clusters.append(['.'.join(key) for key in cluster])
    if len(clusters) > 1:
        groups[name] = clusters
report = {
    'status': 'INCOMPLETE_DISPLAY_INTEGRATION' if missing or mismatches or groups else 'DISPLAY_PAD_TOPOLOGY_ONLY_CHECKED',
    'board_sha256': checkpoint['sha256'],
    'expected_pad_count': len(expected),
    'missing_pads': missing,
    'net_mismatches': mismatches,
    'disconnected_groups_within_display_contract': groups,
    'limitations': [
        'Single present pad on a net does not establish a complete circuit.',
        'This contract inventory excludes upstream rail qualification and CPU endpoints not in the display contracts.',
        'DS1 footprint, flex attachment, mechanical fit and panel datasheet qualification remain necessary.',
        'No electrical simulation, thermal validation or physical operation is implied.'
    ],
    'assembly_ready': False,
}
(D / 'pcb/display-integration-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'missing_pads': len(missing), 'net_mismatches': len(mismatches), 'disconnected_display_nets': len(groups)}))
