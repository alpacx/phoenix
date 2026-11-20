"""Check the cumulative regulator layout and recount physical pad islands on disk."""
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys

import pcbnew as p
from audit_mount_component_reservations import screen
from drc_regression import introduced
from pcb_preservation import verify_preservation

root = Path(__file__).resolve().parents[1] / 'migration-rk3562/experiments/phy-power-parallel'
def read(name):
    return json.loads((root / (name + '.json')).read_text())

def load(report):
    path = root / report['board']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == report['sha256']
    return p.LoadBoard(str(path))

base = read('layout-storage-io')
source = load(base)
checkpoint = read('phy-ground-clearance')
feed = root / 'phy-c516-wide-ground-pad-entry.json'
if feed.exists():
    trial = json.loads(feed.read_text())
    assert trial['parent_sha256'] == checkpoint['sha256']
    if trial['change']:
        checkpoint = trial
storage_rail = '--storage-rail' in sys.argv
bank_feeds = '--bank-feeds' in sys.argv
reg_banks = '--regulator-banks' in sys.argv or bank_feeds
pullups = '--emmc-pullups' in sys.argv or storage_rail or reg_banks
shell = '--usb-shell' in sys.argv or pullups
aux = '--peripheral-supplies' in sys.argv or shell
cap_bank = '--cap-bank' in sys.argv or aux
adjacent = '--adjacent-supplies' in sys.argv or cap_bank
supply40 = '--pin40-powered' in sys.argv or adjacent
pin40 = '--pin40' in sys.argv or supply40
outer = '--outer-ground-mesh' in sys.argv or pin40
mesh = '--core-ground-mesh' in sys.argv or outer
all_ground = '--all-ground-surface' in sys.argv or mesh
full_feed = '--full-feed' in sys.argv or all_ground
opposite = '--opposite-bypass' in sys.argv or full_feed
local_vias = '--local-vias' in sys.argv or opposite
packages = '--package-returns' in sys.argv or local_vias
ground_bends = '--ground-bends' in sys.argv or packages
peripheral = '--peripheral' in sys.argv or ground_bends
additional_pairs = []
if peripheral:
    ext = read('peripheral-returns')
    assert ext['parent_sha256'] == checkpoint['sha256']
    checkpoint = ext
    additional_pairs = [[r['ref']+'.'+r['pad'],'C511.2'] for r in ext['added']]
if ground_bends:
    for name in ('layout-mdio-pullup','ground-doglegs','ground-surface-bends'):
        ext = read(name)
        assert ext['parent_sha256'] == checkpoint['sha256']
        checkpoint = ext
        additional_pairs.extend([ref+'.'+num,'C511.2'] for ref,num,_ in ext.get('added',[]))
if packages:
    for name in ('ground-package-perimeter','package-perimeter-barrels'):
        ext=read(name)
        assert ext['parent_sha256']==checkpoint['sha256'] or (name=='ground-package-perimeter' and ext['parent_sha256']==read('layout-ground-bends')['sha256'])
        checkpoint=ext
        for row in ext['added']:
            ref,num=(row['ref'],row['pad']) if isinstance(row,dict) else row[:2]
            additional_pairs.append([ref+'.'+num,'C511.2'])
if local_vias:
    ext=read('ground-package-local')
    assert ext['parent_sha256']==checkpoint['sha256']
    checkpoint=ext
    additional_pairs.extend([ref+'.'+num,'C511.2'] for ref,num,_ in ext['added'])
if opposite:
    ext=read('opposite-power-bypass')
    assert ext['parent_sha256']==checkpoint['sha256']
    checkpoint=ext
    additional_pairs.extend(row['pair'] for row in ext['records'])
if full_feed:
    proof=read('phy-full-feed-proof')
    assert proof['parent_sha256']==checkpoint['sha256']
    checkpoint=read('phy-joint-terminal-shift')
    assert checkpoint['sha256']==proof['sha256']
    additional_pairs.extend([['C515.1','U5.11'],['R530.2','C516.1']])
if all_ground:
    ext=read('ground-all-local-surface')
    assert ext['parent_sha256']==checkpoint['sha256']
    checkpoint=ext
    additional_pairs.extend([ref+'.'+num,'C511.2'] for ref,num,_ in ext['added'])
if mesh:
    stages=['core-ground-interstitial','core-ground-mesh']
    if outer:stages.extend(['outer-bga-ground','outer-ground-mesh'])
    for name in stages:
        ext=read(name)
        assert ext['parent_sha256']==checkpoint['sha256']
        checkpoint=ext
        for row in ext['added']:
            ref,num=(row['ref'],row['pad']) if isinstance(row,dict) else row[:2]
            additional_pairs.append([ref+'.'+num,'C511.2'])
if pin40:
    ext=read('phy-pin40-integrated')
    assert ext['parent_sha256']==checkpoint['sha256']
    checkpoint=ext
    additional_pairs.extend(ext['pairs'])
if supply40:
    for name in ('phy-pin40-5v-clearance','phy-pin40-supply-offset-5v-clear'):
        ext=read(name)
        assert ext['change'] and ext['parent_sha256']==checkpoint['sha256']
        checkpoint=ext
    additional_pairs.append(['C515.1','U5.40'])
if adjacent:
    stages=['package-adjacent-supplies']
    if cap_bank:stages.append('local-cap-bank')
    if aux:stages.append('peripheral-supply-balls')
    for name in stages:
        ext=read(name)
        assert ext['parent_sha256']==checkpoint['sha256']
        checkpoint=ext
        additional_pairs.extend(row['pair'] for row in ext['records'])
if shell:
    for stage in ('usb-shell-tabs','usb-shell-inner'):
        ext=read(stage)
        assert ext['parent_sha256']==checkpoint['sha256']
        checkpoint=ext
if pullups:
    stages=['emmc-pullup-supply']
    if reg_banks:stages.append('regulator-banks')
    if bank_feeds:stages.append('bank-feeds')
    if storage_rail:stages.append('storage-rail-groups')
    for name in stages:
        ext=read(name)
        assert ext['parent_sha256']==checkpoint['sha256']
        checkpoint=ext
        additional_pairs.extend(row['pair'] for row in ext['records'])
board = load(checkpoint)
if shell:
    tabs=[q for q in board.FindFootprintByReference('J1').Pads() if q.GetNetname()=='USB_SHIELD']
    assert len(tabs)==4
    group={k.m_Uuid.AsString() for k in board.GetConnectivity().GetConnectedItems(tabs[0])}
    assert all(q.m_Uuid.AsString() in group for q in tabs)
    assert not any(q.m_Uuid.AsString() in group for f in board.GetFootprints() for q in f.Pads() if q.GetNetname()!='USB_SHIELD')
path = root / checkpoint['board']
basepath = root / base['board']
for ext in ('.kicad_pro', '.kicad_dru'):
    assert path.with_suffix(ext).read_bytes() == basepath.with_suffix(ext).read_bytes()
original = {t.m_Uuid.AsString() for t in source.GetTracks()}
replaced = set()
for stage in ('phy-pin11-bypass', 'phy-switch-entry', 'phy-thermal-power-joint', 'phy-ground-clearance'):
    replaced.update(read(stage)['change']['preservation']['explicitly_replaced_copper'])
if pin40:replaced.update(read('phy-pin40-integrated')['preservation']['explicitly_replaced_copper'])
if supply40:replaced.update(read('phy-pin40-5v-clearance')['change']['preservation']['explicitly_replaced_copper'])
preservation = verify_preservation(source, board, replaced_copper=replaced & original)
assert not screen(board)
thermal_ids = set(read('phy-thermal-power-joint')['change']['via_ids'])
thermal = [v for v in board.GetTracks() if v.m_Uuid.AsString() in thermal_ids]
assert len(thermal) == 1
assert thermal[0].GetFillingMode() == p.FILLING_MODE_FILLED and thermal[0].GetCappingMode() == p.CAPPING_MODE_CAPPED
nets = defaultdict(list)
for f in board.GetFootprints():
    for pad in f.Pads():
        if pad.GetNetCode() and pad.GetNumber():
            nets[pad.GetNetname()].append((f.GetReference()+'.'+pad.GetNumber(), pad))
unresolved = {}
membership = defaultdict(set)
for net, pads in nets.items():
    seen = set()
    groups = []
    for name, pad in pads:
        uid = pad.m_Uuid.AsString()
        if uid in seen:
            continue
        ids = {i.m_Uuid.AsString() for i in board.GetConnectivity().GetConnectedItems(pad)} | {uid}
        seen.update(ids)
        names = sorted(n for n, q in pads if q.m_Uuid.AsString() in ids)
        groups.append(names)
        for n in names:
            membership[n].add((net,len(groups)))
    if len(groups) > 1:
        unresolved[net] = groups
pairs = base['verified_pairs'] + additional_pairs + [['U5.30','L501.1'],['L501.2','C511.1'],['C516.1','U5.11'],['U5.41','C511.2']]
for a,z in pairs:
    assert membership[a] & membership[z], (a,z)
with tempfile.TemporaryDirectory() as tmp:
    result = Path(tmp)/'drc.json'
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(result),str(path)],check=True,capture_output=True)
    report=json.loads(result.read_text())
delta = introduced(json.loads((basepath.parent/'drc.json').read_text()),report)
assert not delta, delta
output = dict(board=checkpoint['board'],sha256=checkpoint['sha256'],parent_sha256=base['sha256'],verified_pairs=pairs,preservation=preservation,open_nets=unresolved,remaining_minimum_joins=sum(len(g)-1 for g in unresolved.values()),new_drc=delta,drc_counts=Counter(v['type'] for v in report['violations']),assembly_ready=False)
(root/('layout-bank-feeds.json' if bank_feeds else 'layout-regulator-banks.json' if reg_banks else 'layout-storage-rail.json' if storage_rail else 'layout-emmc-pullups.json' if pullups else 'layout-usb-shell.json' if shell else 'layout-peripheral-supply-balls.json' if aux else 'layout-cap-bank.json' if cap_bank else 'layout-adjacent-supplies.json' if adjacent else 'layout-phy-pin40-powered.json' if supply40 else 'layout-phy-pin40.json' if pin40 else 'layout-outer-ground-mesh.json' if outer else 'layout-core-ground-mesh.json' if mesh else 'layout-all-ground-surface.json' if all_ground else 'layout-phy-full-feed.json' if full_feed else 'layout-opposite-bypass.json' if opposite else 'layout-package-local.json' if local_vias else 'layout-package-returns.json' if packages else 'layout-ground-bends.json' if ground_bends else 'layout-peripheral-returns.json' if peripheral else 'layout-regulator-joint.json')).write_text(json.dumps(output,indent=2)+'\n')
print(len(pairs),len(unresolved),output['remaining_minimum_joins'],output['drc_counts'],flush=True)
os._exit(0)
