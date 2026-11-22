"""Recover electrical contracts across a relocated PMIC coupon from pad-instance connectivity."""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import os
import sys
import pcbnew as p

root = Path(__file__).resolve().parents[1] / 'migration-rk3562/experiments/phy-power-parallel'
checkpoint = json.loads((root / 'layout-pmic-pwron-filter.json').read_text())
folder = root / 'runs' / (sys.argv[1] if len(sys.argv) > 1 else 'pmic-five-stage-c425-r410-0')
coupon = json.loads((folder / 'output-legs.json').read_text())


def load(path, sha):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    board = p.LoadBoard(str(path))
    board.BuildConnectivity()
    return board


def groups(board):
    pads = {q.m_Uuid.AsString(): q for f in board.GetFootprints() for q in f.Pads() if q.GetNetCode() and q.GetNumber()}
    labels = {uid: q.GetParentFootprint().GetReference() + '.' + q.GetNumber() for uid, q in pads.items()}
    components = {}
    for uid, q in pads.items():
        if uid in components:
            continue
        connected = {item.m_Uuid.AsString() for item in board.GetConnectivity().GetConnectedItems(q)}
        group = frozenset(({uid} | connected) & pads.keys())
        for member in group:
            assert pads[member].GetNetname() == q.GetNetname()
            components[member] = group
    return pads, labels, components


original = load(root / checkpoint['board'], checkpoint['sha256'])
current = load(folder / 'phy-joint.kicad_pcb', coupon['board_sha256'])
before, labels, old = groups(original)
after, names, new = groups(current)
assert labels == names and all(before[k].GetNetname() == after[k].GetNetname() for k in before)
broken = defaultdict(list)
for group in set(old.values()):
    parts = {new[k] & group for k in group}
    if len(parts) > 1:
        broken[before[next(iter(group))].GetNetname()].append(sorted([sorted(labels[k] for k in part) for part in parts]))
lookup = defaultdict(set)
for k, name in labels.items():
    lookup[name].add(k)
lost = []
for left, right in checkpoint['verified_pairs']:
    assert any(old[k] & lookup[right] for k in lookup[left])
    if not any(new[k] & lookup[right] for k in lookup[left]):
        lost.append([left, right])
report = dict(source_sha256=checkpoint['sha256'], coupon_sha256=coupon['board_sha256'],
              pad_instances=len(before), lost_verified_pairs=lost, preserved_verified_pairs=len(checkpoint['verified_pairs'])-len(lost),
              split_prior_groups=dict(sorted((name,sorted(sets)) for name,sets in broken.items())),
              minimum_repairs_to_recover_original_groups=sum(len(g)-1 for sets in broken.values() for g in sets),
              prior_minimum_joins=sum(len(g)-1 for g in checkpoint['open_nets'].values()),
              coupon_minimum_joins=len(set(new.values()))-len({q.GetNetname() for q in after.values()}))
def joined(a,z):
    return any(new[k] & lookup[z] for k in lookup[a])


report['power_circuits']={}
for stage,pins in enumerate([('12','11'),('9','10'),('25','24'),('65','66'),('53','54')],1):
    switch,vin=pins
    terminals={'phase':('U4.'+switch,f'L40{stage}.1'),
               'positive':(f'L40{stage}.2',f'C43{stage}.1'),
               'input':('U4.'+vin,f'C42{stage}.1'),
               'output_ground':(f'C43{stage}.2','U4.69'),
               'input_ground':(f'C42{stage}.2','U4.69')}
    if stage==5:
        terminals.update(feedback=('U4.59','C435.1'),secondary=('C435.1','C445.1'),
                         secondary_ground=('C445.2','U4.69'))
    # Net consistency also catches incorrect pin aliases in a project-specific audit.
    for a,z in terminals.values():
        assert {after[k].GetNetname() for k in lookup[a]}=={after[k].GetNetname() for k in lookup[z]},(a,z)
    report['power_circuits'][stage]={name:{'pads':[a,z],'native_connected':joined(a,z)} for name,(a,z) in terminals.items()}
report['voltage_detector']={label:joined(a,z) for label,a,z in [
    ('pin_to_filter','U4.61','C410.1'),('upper_to_filter','R410.2','C410.1'),
    ('lower_to_filter','R411.1','C410.1'),('upper_supply','R410.1','C1304.1'),
    ('lower_ground','R411.2','U4.69'),('filter_ground','C410.2','U4.69')]}
(folder / 'boundary-contracts.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['preserved_verified_pairs'], report['minimum_repairs_to_recover_original_groups'], report['coupon_minimum_joins'], sorted(broken), flush=True)
os._exit(0)
