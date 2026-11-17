#!/usr/bin/env python3
"""Inventory actual PHY power connectivity without adding unqualified power copper."""
import hashlib
import json
from pathlib import Path
import pcbnew as p

D = Path(__file__).resolve().parents[1] / 'migration-rk3562/experiments/pmic-ldo-inputs'
checkpoint = json.loads((D / 'working-candidate.json').read_text())
source = D / checkpoint['board']
assert hashlib.sha256(source.read_bytes()).hexdigest() == checkpoint['sha256']
b = p.LoadBoard(str(source))
b.BuildConnectivity()
pads = {(f.GetReference(), q.GetNumber()): q for f in b.GetFootprints() for q in f.Pads()}
nets = ['PHY_SW', '+1V0_PHY', '+3V3_PHY']
rows = []
for net in nets:
    members = {key: pad for key, pad in pads.items() if pad.GetNetname() == net}
    remaining = set(members)
    groups = []
    while remaining:
        seed = min(remaining)
        reached = {q.m_Uuid.AsString() for q in b.GetConnectivity().GetConnectedItems(members[seed])}
        reached.add(members[seed].m_Uuid.AsString())
        group = sorted(key for key in remaining if members[key].m_Uuid.AsString() in reached)
        assert seed in group
        remaining.difference_update(group)
        groups.append(['.'.join(key) for key in group])
    rows.append({'net': net, 'pad_count': len(members), 'connected_pad_groups': groups,
                 'minimum_joins': max(0, len(groups)-1),
                 'pads': [{'pad': '.'.join(key), 'position_mm': [p.ToMM(q.GetPosition().x), p.ToMM(q.GetPosition().y)],
                           'direct_copper_items': len(b.GetConnectivity().GetConnectedTracks(q))}
                          for key, q in sorted(members.items())]})
result = {'status': 'CONNECTIVITY_INVENTORY_NOT_POWER_QUALIFICATION',
          'source_sha256': checkpoint['sha256'], 'nets': rows,
          'minimum_joins': sum(row['minimum_joins'] for row in rows),
          'checkpoint_modified': False, 'assembly_ready': False,
          'limitations': ['Minimum joins are topological, not track counts.',
                         'Existing thin bypass copper can join pads without being adequate as a power distribution path.',
                         'Current capacity, return loops, regulator stability and oscillator coupling remain unqualified.']}
assert hashlib.sha256(source.read_bytes()).hexdigest() == checkpoint['sha256']
(D / 'pcb/phy-power-topology.json').write_text(json.dumps(result, indent=2)+'\n')
for row in rows:
    print(row['net'], len(row['connected_pad_groups']), 'groups;', row['minimum_joins'], 'minimum joins')
