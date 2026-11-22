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
ca1='--command-ca1' in sys.argv
emmc_data='--emmc-data-power' in sys.argv or ca1
n12_near='--n12-neighbors' in sys.argv or emmc_data
n12_supply='--n12-supply' in sys.argv or n12_near
zq_supply='--zq-supply' in sys.argv or n12_supply
wide_trunks='--wide-memory-trunks' in sys.argv or zq_supply
vddq_trunk='--vddq-trunk' in sys.argv or wide_trunks
vdd1_trunk='--vdd1-trunk' in sys.argv or vddq_trunk
vdd1_bank='--vdd1-bank' in sys.argv or vdd1_trunk
radio_returns='--radio-returns' in sys.argv or vdd1_bank
radio_wake='--radio-wake' in sys.argv or radio_returns
gpu_bank = '--gpu-cap-bank' in sys.argv or radio_wake
cap_return = '--memory-cap-return' in sys.argv or gpu_bank
bank_rear = '--memory-bank-rear-taps' in sys.argv or cap_return
ab4_bank = '--memory-ab4-bank' in sys.argv or bank_rear
ab4 = '--memory-ab4-bypass' in sys.argv or ab4_bank
offset_ground = '--ground-land-offsets' in sys.argv or ab4
memory_ground = '--memory-ground-neighbors' in sys.argv or offset_ground
soc_ground = '--soc-ground-neighbors' in sys.argv or memory_ground
core_neighbors = '--soc-core-neighbors' in sys.argv or soc_ground
mux_dir = '--usb-direction-complete' in sys.argv or core_neighbors
memory_local = '--memory-bank-c1665' in sys.argv or mux_dir
emmc_perimeter = '--emmc-perimeter-supply' in sys.argv or memory_local
emmc_adjacent = '--emmc-adjacent-supply' in sys.argv or emmc_perimeter
analog_1v8 = '--usb-analog-1v8' in sys.argv or emmc_adjacent
analog_0v9 = '--usb-analog-0v9' in sys.argv or analog_1v8
mux_enable = '--usb-enable-trunk' in sys.argv or analog_0v9
lcd_cs = '--lcd-select-trunk' in sys.argv or mux_enable
lcd_clock = '--lcd-clock-trunk' in sys.argv or lcd_cs
cpu_enable = '--cpu-enable-bias' in sys.argv or lcd_clock
spi0_pullup = '--exp-spi0-pullup' in sys.argv or cpu_enable
sda_complete = '--exp-sda-complete' in sys.argv or spi0_pullup
sda_land = '--exp-sda-land' in sys.argv or sda_complete
wifi_io_bank = '--wifi-bank-feed' in sys.argv or sda_land
exp_data = '--exp-data-pullup' in sys.argv or wifi_io_bank
exp_clock = '--exp-clock-pullup' in sys.argv or exp_data
dq0_reference = '--lpddr-dq0-reference' in sys.argv or exp_clock
clock_return = '--lpddr-clock-return' in sys.argv or dq0_reference
pwron_filter = '--pmic-pwron-filter' in sys.argv or clock_return
tx_series = '--soc-tx-series' in sys.argv or pwron_filter
rx_series = '--phy-source-series' in sys.argv or tx_series
hanrun = '--hanrun-hole-stagger' in sys.argv or rx_series
coincident = '--coincident-cleanup' in sys.argv or hanrun
cpu_load = '--cpu-load-sense' in sys.argv or coincident
power_probes = '--power-probes' in sys.argv or cpu_load
wifi_bias = '--wifi-sdio-bias' in sys.argv or power_probes
aux_cap_banks = '--aux-cap-banks' in sys.argv or wifi_bias
ram_cap_bank = '--ram-cap-bank' in sys.argv or aux_cap_banks
island_barrels = '--ground-island-barrels' in sys.argv or ram_cap_bank
island_mesh = '--island-mesh' in sys.argv or island_barrels
island_returns = '--island-returns' in sys.argv or island_mesh
supply_islands = '--supply-islands' in sys.argv or island_returns
ground_islands = '--ground-islands' in sys.argv or supply_islands
bank_feeds = '--bank-feeds' in sys.argv or ground_islands
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
    if ground_islands:stages.append('ground-short-islands')
    if supply_islands:stages.append('supply-short-islands')
    if island_returns:stages.append('island-returns')
    if storage_rail:stages.append('storage-rail-groups')
    for name in stages:
        ext=read(name)
        assert ext['parent_sha256']==checkpoint['sha256']
        checkpoint=ext
        additional_pairs.extend(row['pair'] for row in ext['records'])
if island_mesh:
    ext=read('island-mesh')
    assert ext['parent_sha256']==checkpoint['sha256']
    additional_pairs.extend([[f'{ref}.{num}','C511.2'] for ref,num,length in ext['added']])
    checkpoint=ext
if island_barrels:
    ext=read('ground-island-barrels')
    assert ext['parent_sha256']==checkpoint['sha256']
    additional_pairs.extend([[row['ref']+'.'+row['pad'],'C511.2'] for row in ext['added']])
    checkpoint=ext
if ram_cap_bank:
    ext=read('ram-cap-bank')
    assert ext['parent_sha256']==checkpoint['sha256']
    additional_pairs.extend(row['pair'] for row in ext['records'])
    checkpoint=ext
if aux_cap_banks:
    ext=read('aux-cap-banks')
    assert ext['parent_sha256']==checkpoint['sha256']
    additional_pairs.extend(row['pair'] for row in ext['records'])
    checkpoint=ext
if wifi_bias:
    ext=read('wifi-sdio-bias')
    assert ext['parent_sha256']==checkpoint['sha256']
    additional_pairs.extend(row['pair'] for row in ext['records'])
    checkpoint=ext
if power_probes:
    ext=read('power-probes')
    assert ext['parent_sha256']==checkpoint['sha256']
    additional_pairs.extend(row['pair'] for row in ext['records'])
    checkpoint=ext
if cpu_load:
    ext=read('cpu-load-probe')
    assert ext['parent_sha256']==checkpoint['sha256']
    additional_pairs.extend(row['pair'] for row in ext['records'])
    checkpoint=ext
if coincident:
    ext=read('coincident-track-cleanup')
    assert ext['parent_sha256']==checkpoint['sha256']
    checkpoint=ext
if hanrun:
    ext=read('hanrun-hole-stagger')
    assert ext['parent_sha256']==checkpoint['sha256'] and not ext['new_drc']
    checkpoint=ext
if rx_series:
    ext=read('phy-source-series')
    assert ext['parent_sha256']==checkpoint['sha256']
    additional_pairs.extend(r['pair'] for r in ext['records'] if r['adopted'])
    checkpoint=ext
if tx_series:
    ext=read('soc-tx-series')
    assert ext['parent_sha256']==checkpoint['sha256']
    additional_pairs.extend(r['pair'] for r in ext['records'] if r['adopted'])
    checkpoint=ext
if pwron_filter:
    ext=read('pmic-pwron-rear-filter')
    assert ext['parent_sha256']==checkpoint['sha256'] and ext['adopted']
    additional_pairs.extend([ext['pair'],['C412.2','U4.69']])
    checkpoint=ext
if clock_return:
    ext=read('lpddr-clock-return-stitches')
    assert ext['parent_sha256']==checkpoint['sha256'] and not ext['new_drc']
    vias=[r['accepted']['via_uuid'] for r in ext['terminal_results'] if r['accepted']]
    assert len(vias)==3
    checkpoint=ext
if dq0_reference:
    ext=read('lpddr-dq0-reference')
    assert ext['parent_sha256']==checkpoint['sha256'] and ext['accepted']
    assert ext['attempts'][-1]['supported']==ext['source_window_points']
    assert not ext['attempts'][-1]['new_reference_losses']
    checkpoint=ext
if exp_clock:
    ext=read('exp-clock-pullup-feed')
    assert ext['parent_sha256']==checkpoint['sha256'] and len(ext['records'])==1
    additional_pairs.extend([ext['records'][0]['pair'],['U4.55','R2102.2'],['R2102.1','J3.24']])
    checkpoint=ext
if exp_data:
    ext=read('exp-data-pullup-feed')
    assert ext['parent_sha256']==checkpoint['sha256'] and len(ext['records'])==1
    additional_pairs.extend([ext['records'][0]['pair'],['U4.55','R2101.2']])
    checkpoint=ext
if wifi_io_bank:
    ext=read('wifi-io-pullup-bank-feed')
    assert ext['parent_sha256']==checkpoint['sha256']
    assert {row['pair'][1] for row in ext['records']}=={'R2010.2','R2012.2','R2013.2','R2014.2'}
    additional_pairs.extend(row['pair'] for row in ext['records'])
    additional_pairs.append(['R2012.1','U25.14'])
    checkpoint=ext
if sda_land:
    stage=read('exp-sda-dual-land')
    assert stage['parent_sha256']==checkpoint['sha256'] and not stage['candidate']['new_drc']
    checkpoint=dict(stage['candidate'],parent_sha256=stage['parent_sha256'])
    additional_pairs.append(['J3.23','R2101.1'])
if sda_complete:
    launch=read('exp-sda-soc-launch')
    route=read('exp-sda-complete')
    assert launch['parent_sha256']==checkpoint['sha256'] and route['parent_sha256']==launch['candidate']['sha256']
    assert len(route['records'])==1 and set(route['records'][0]['pair'])=={'J3.23','U1.AE15'}
    additional_pairs.extend([['J3.23','U1.AE15'],['U1.AE15','R2101.1']])
    # The incomplete launch is an intermediate coupon. Keep the immediately
    # preceding adopted PCB in the checkpoint's ancestry.
    checkpoint=dict(route,parent_sha256=checkpoint['sha256'])
if spi0_pullup:
    local=read('spi0-local-signal')
    rail=read('exp-spi0-restore-feed')
    assert local['parent_sha256']==checkpoint['sha256'] and rail['parent_sha256']==local['candidate']['sha256']
    assert len(rail['records'])==1
    final_board=load(rail)
    local_replaced=set(local['candidate']['preservation']['explicitly_replaced_copper'])
    verify_preservation(load(checkpoint),final_board,replaced_copper=local_replaced)
    additional_pairs.extend([['J3.34','U1.AG17'],['U1.AG17','R2103.1'],['TP5.1','R2103.2']])
    checkpoint=dict(rail,parent_sha256=checkpoint['sha256'])
if cpu_enable:
    elbow=read('cpu-enable-vbat-elbow')
    rail=read('cpu-enable-elbow-route')
    assert elbow['parent_sha256']==checkpoint['sha256'] and rail['parent_sha256']==elbow['candidate']['sha256']
    assert elbow['candidate']['reworked_width_mm']==1.0 and elbow['candidate']['length_delta_mm']<=.5
    assert len(rail['records'])==1 and 'R1002.1' in rail['records'][0]['pair']
    en_replaced=set(elbow['candidate']['preservation']['explicitly_replaced_copper'])
    verify_preservation(load(checkpoint),load(rail),replaced_copper=en_replaced)
    additional_pairs.extend([['R417.1','R1002.1'],['R1002.2','U10.A2']])
    checkpoint=dict(rail,parent_sha256=checkpoint['sha256'])
if lcd_clock:
    launch=read('lcd-clock-soc-launch')
    route=read('lcd-clock-grid-route')
    assert launch['parent_sha256']==checkpoint['sha256'] and route['parent_sha256']==launch['candidate']['sha256']
    assert len(route['records'])==1 and set(route['records'][0]['pair'])=={'U21.3','U1.N3'}
    verify_preservation(load(checkpoint),load(route))
    additional_pairs.extend([['U1.N3','U21.3'],['U1.N3','R1812.1']])
    checkpoint=dict(route,parent_sha256=checkpoint['sha256'])
if lcd_cs:
    launch=read('display-cs-gnd-fanout')
    route=read('lcd-select-grid-route')
    assert launch['parent_sha256']==checkpoint['sha256'] and route['parent_sha256']==launch['candidate']['sha256']
    assert len(route['records'])==1 and set(route['records'][0]['pair'])=={'R1815.1','U1.M3'}
    cs_ground_replaced=set(launch['candidate']['preservation']['explicitly_replaced_copper'])
    verify_preservation(load(checkpoint),load(route),replaced_copper=cs_ground_replaced)
    additional_pairs.extend([['U1.M3','U21.6'],['U1.M3','R1815.1']])
    checkpoint=dict(route,parent_sha256=checkpoint['sha256'])
if mux_enable:
    launch=read('usb-enable-aon-fanout');route=read('usb-mux-enable-trunk')
    assert launch['parent_sha256']==checkpoint['sha256'] and route['parent_sha256']==launch['candidate']['sha256']
    assert len(route['records'])==1 and set(route['records'][0]['pair'])=={'U6.12','U16.4'}
    mux_replaced=set(launch['candidate']['preservation']['explicitly_replaced_copper'])
    verify_preservation(load(checkpoint),load(route),replaced_copper=mux_replaced)
    additional_pairs.append(['U6.12','U16.4'])
    checkpoint=dict(route,parent_sha256=checkpoint['sha256'])
if analog_0v9:
    stage=read('usb-analog-0v9-filter')
    assert stage['parent_sha256']==checkpoint['sha256']
    checkpoint=stage
    additional_pairs.extend(stage['pairs'])
if analog_1v8:
    analog_parent=checkpoint['sha256']
    for name in ('rf-edge-r1602-recovery-main','usb-analog-1v8-c1682-restored'):
        stage=read(name)
        assert stage['parent_sha256']==checkpoint['sha256']
        checkpoint=stage['result'][0]
    additional_pairs.extend([['R1602.1','C1635.1'],['R1602.2','C1682.1'],['C1682.2','U4.69']])
if emmc_adjacent:
    ext=read('emmc-adjacent-supply-lands')
    assert ext['parent_sha256']==checkpoint['sha256'] and not ext['new_drc']
    checkpoint=ext
    additional_pairs.extend(row['pair'] for row in ext['accepted'])
if emmc_perimeter:
    ext=read('emmc-perimeter-supply')
    assert ext['parent_sha256']==checkpoint['sha256'] and not ext['new_drc']
    checkpoint=ext
    additional_pairs.extend(row['pair'] for row in ext['accepted'])
if memory_local:
    step=read('memory-w1-c1665-local-bank-C1666-rail-plane-radius')
    assert step['parent_sha256']==checkpoint['sha256']
    candidate=step['result'][0]
    assert not candidate['new_drc']
    replaced_memory=set(candidate['preservation']['explicitly_replaced_copper'])
    verify_preservation(load(checkpoint),load(candidate),replaced_copper=replaced_memory)
    additional_pairs.extend([['C1665.1','C1666.1'],['C1665.2','U4.69']])
    checkpoint=dict(candidate,parent_sha256=checkpoint['sha256'])
if mux_dir:
    launch=read('usb-orientation-released-escape')
    trunk=read('usb-orientation-trunk')
    assert launch['parent_sha256']==checkpoint['sha256'] and trunk['parent_sha256']==launch['candidate']['sha256']
    assert [sorted(record['pair']) for record in trunk['records']]==[['R602.2','U6.11']]
    verify_preservation(load(checkpoint),load(trunk))
    additional_pairs.append(['R602.2','U6.11'])
    checkpoint=dict(trunk,parent_sha256=checkpoint['sha256'])
if core_neighbors:
    stage=read('soc-core-neighbors')
    assert stage['parent_sha256']==checkpoint['sha256'] and not stage['new_drc']
    assert all(row['width_mm']==.5 for row in stage['accepted'])
    verify_preservation(load(checkpoint),load(stage))
    additional_pairs.extend(row['pair'] for row in stage['accepted'])
    checkpoint=stage
for active,name in ((soc_ground,'soc-ground-neighbors'),(memory_ground,'memory-ground-neighbors')):
    if active:
        stage=read(name)
        assert stage['parent_sha256']==checkpoint['sha256'] and not stage['new_drc']
        assert all(row['width_mm']>=.3 and row['net']=='GND' for row in stage['accepted'])
        verify_preservation(load(checkpoint),load(stage))
        additional_pairs.extend(row['pair'] for row in stage['accepted'])
        checkpoint=stage
if offset_ground:
    stage=read('ground-land-offsets')
    assert stage['parent_sha256']==checkpoint['sha256']
    verify_preservation(load(checkpoint),load(stage))
    additional_pairs.extend([[ref+'.'+num,'U4.69'] for ref,num,length in stage['added']])
    checkpoint=stage
if ab4:
    study=read('memory-ab4-bypass-placement')
    assert study['parent_sha256']==checkpoint['sha256']
    stage=study['candidate']
    before_ref,after_ref=read('lpddr-return-before-ab4'),read('lpddr-return-after-ab4')
    assert before_ref['source_sha256']==checkpoint['sha256'] and after_ref['source_sha256']==stage['sha256']
    assert not after_ref['foreign_or_unattributed'] and before_ref['estimated_length_mm']==after_ref['estimated_length_mm']
    assert not stage['new_drc']
    ab4_retired=set(stage['preservation']['explicitly_replaced_copper'])
    verify_preservation(load(checkpoint),load(stage),replaced_copper=ab4_retired)
    additional_pairs.extend([['U2.AB4','C1674.1'],['C1674.2','U4.69']])
    checkpoint=dict(stage,parent_sha256=checkpoint['sha256'])
if ab4_bank:
    study=read('memory-ab4-bank-bent')
    assert study['parent_sha256']==checkpoint['sha256'] and study['candidate']['new_drc']==[]
    candidate=study['candidate']
    verify_preservation(load(checkpoint),load(candidate))
    signal_ref=read('memory-bank-inner-reference-comparison')
    assert signal_ref['sha256']==candidate['sha256'] and signal_ref['base_sha256']==checkpoint['sha256']
    assert all(row['increase_mm2']<1e-6 for item in signal_ref['records'] for row in item['projection'])
    projection=read('lpddr-return-after-bank')
    assert projection['source_sha256']==candidate['sha256'] and not projection['foreign_or_unattributed']
    assert projection['estimated_length_mm']==read('lpddr-return-after-ab4')['estimated_length_mm']
    broadside=read('memory-ab4-bank-broadside')
    assert broadside['candidate_sha256']==candidate['sha256']
    assert all(item['net']=='+3V3_IO' for layer in broadside['fields'] for item in layer['objects'])
    normalized=read('memory-ab4-normalized')
    assert normalized['parent_sha256']==candidate['sha256'] and not normalized['new_drc'] and not normalized['mounts']
    verify_preservation(load(candidate),load(normalized),replaced_copper=normalized['wholly_contained_tracks'])
    additional_pairs.append(['U2.AB4','C1666.1'])
    checkpoint=dict(normalized,parent_sha256=checkpoint['sha256'])
if bank_rear:
    stage=read('memory-bank-rear-taps')
    assert stage['parent_sha256']==checkpoint['sha256'] and not stage['new_drc'] and not stage['mounts']
    verify_preservation(load(checkpoint),load(stage))
    additional_pairs.extend([[r['ref']+'.1','U2.AB4'] for r in stage['steps'] if r['path_nm']])
    checkpoint=stage
if cap_return:
    study=read('memory-bank-cap-and-return')
    assert study['parent_sha256']==checkpoint['sha256']
    stage=study['candidate']
    projection=read('memory-bank-cap-return-projection')
    assert projection['sha256']==stage['sha256'] and projection['base_sha256']==checkpoint['sha256']
    assert all(row['increase_mm2']<1e-6 for item in projection['records'] for row in item['projection'])
    assert all(row['nearest_after_mm']<=row['nearest_before_mm'] for row in projection['nearby_signal_vias'])
    clock=read('lpddr-return-after-cap-return')
    assert clock['source_sha256']==stage['sha256'] and clock['estimated_length_mm']==read('lpddr-return-after-bank')['estimated_length_mm']
    assert not stage['new_drc']
    carried=set(stage['preservation']['explicitly_replaced_copper'])
    verify_preservation(load(checkpoint),load(stage),replaced_copper=carried)
    additional_pairs.append(['C1663.1','U2.AB4'])
    checkpoint=dict(stage,parent_sha256=checkpoint['sha256'])
if gpu_bank:
    stage=read('soc-gpu-rear-bank')
    assert stage['parent_sha256']==checkpoint['sha256'] and not stage['new_drc'] and not stage['mounts']
    verify_preservation(load(checkpoint),load(stage))
    additional_pairs.extend([['C1619.1','C1620.1'],['C1619.2','U4.69'],['C1620.2','U4.69']])
    checkpoint=stage
if radio_wake:
    soc=read('wifi_host_wake-service-launch')
    assert soc['parent_sha256']==checkpoint['sha256']
    radio=read('radio-wake-reset-rework')
    assert radio['parent_sha256']==soc['candidate']['sha256']
    restored=radio['candidate']
    radio_replaced=set(restored['replaced'])
    stage=read('radio-wake-complete')
    assert stage['parent_sha256']==restored['sha256']
    verify_preservation(load(checkpoint),load(stage),replaced_copper=radio_replaced)
    additional_pairs.append(['U1.V26','U25.13'])
    checkpoint=dict(stage,parent_sha256=checkpoint['sha256'])
if radio_returns:
    stage=read('radio-wake-return-stitches')
    assert checkpoint['sha256']==stage['parent_sha256'] and not stage['new_drc']
    radio_vias=[r['accepted']['via_uuid'] for r in stage['terminal_results'] if r['accepted']]
    assert len(radio_vias)==2
    vias=list(vias)+radio_vias
    verify_preservation(load(checkpoint),load(stage))
    checkpoint=stage
if vdd1_bank:
    stage=read('soc-vdd1-rear-bank')
    assert checkpoint['sha256']==stage['parent_sha256'] and not stage['new_drc'] and not stage['mounts']
    verify_preservation(load(checkpoint),load(stage))
    additional_pairs.extend([['C2302.1','U2.F1'],['C2304.1','U2.F1'],['C2306.1','U2.F1'],['C2307.1','U2.F1']])
    checkpoint=stage
if vdd1_trunk:
    launch=read('vdd1-external-pair')
    assert launch['parent_sha256']==checkpoint['sha256']
    source_pair=launch['candidate']
    vdd1_replaced={source_pair['resized']}
    assert len(set(source_pair['barrels']))==2
    stage=read('vdd1-external-pair-trunk')
    assert stage['parent_sha256']==source_pair['sha256'] and not stage['held']
    verify_preservation(load(checkpoint),load(stage),replaced_copper=vdd1_replaced)
    additional_pairs.extend([['L405.2','U2.F1'],['U4.59','C2305.1']])
    checkpoint=dict(stage,parent_sha256=checkpoint['sha256'])
if vddq_trunk:
    stage=read('vddq-trimmed-mosi')
    assert stage['parent_sha256']==checkpoint['sha256'] and not stage['new_drc']
    vddq_replaced=set(stage['replaced'])
    verify_preservation(load(checkpoint),load(stage),replaced_copper=vddq_replaced)
    additional_pairs.extend([['L403.2','U2.AB4'],['L403.2','C1666.1'],['J3.32','U1.AG19']])
    checkpoint=stage
if wide_trunks:
    stage=read('memory-trunk-widths')
    projection=read('memory-trunk-widths-projection')
    assert stage['parent_sha256']==projection['before']==checkpoint['sha256']
    assert projection['after']==stage['sha256'] and not stage['new_drc'] and not stage['mounts']
    assert all(m['removed_mm2']==m['added_mm2']==0 for m in projection['filled_ground_difference'])
    wide_replaced=set(stage['replaced'])
    verify_preservation(load(checkpoint),load(stage),replaced_copper=wide_replaced)
    checkpoint=stage
if zq_supply:
    local=read('ram-front-zq')
    assert local['parent_sha256']==checkpoint['sha256'] and not local['new_drc'] and not local['mounts']
    stage=read('vddq-zq-source')
    assert stage['parent_sha256']==local['sha256'] and stage['records'] and not stage['held']
    verify_preservation(load(checkpoint),load(stage))
    additional_pairs.extend([['R201.2','U2.A4'],['L403.2','U2.A4'],['R201.1','U2.A5']])
    checkpoint=dict(stage,parent_sha256=checkpoint['sha256'])
if n12_supply:
    fan=read('memory-n12-escape')
    assert fan['parent_sha256']==checkpoint['sha256']
    stage=read('vddq-n12-source')
    assert stage['parent_sha256']==fan['candidate']['sha256'] and stage['records'] and not stage['held']
    impact=read('memory-n12-plane-impact')
    assert impact['base_sha256']==checkpoint['sha256'] and impact['sha256']==stage['sha256']
    assert not any(row['increase_mm2']>1e-6 for rec in impact['records'] for row in rec['projection'])
    verify_preservation(load(checkpoint),load(stage))
    additional_pairs.append(['L403.2','U2.N12'])
    checkpoint=dict(stage,parent_sha256=checkpoint['sha256'])
if n12_near:
    stage=read('ram-n12-neighbors')
    assert stage['parent_sha256']==checkpoint['sha256'] and not stage['new_drc'] and not stage['mounts']
    verify_preservation(load(checkpoint),load(stage))
    for row in stage['steps']:
        if row['path_nm']:
            additional_pairs.append(['L403.2', row['ref']+'.'+row['pad']])
    checkpoint=stage
if emmc_data:
    pivot=read('emmc-io-link-return-window')
    assert pivot['parent_sha256']==checkpoint['sha256']
    pivot=pivot['candidate']
    moved=read('emmc-io-link-keep-pullup')
    assert moved['parent_sha256']==pivot['sha256']
    moved=moved['candidate']
    supply=read('emmc-vccq-moved-link-source')
    assert supply['parent_sha256']==moved['sha256'] and supply['records'] and not supply['held']
    launch=read('emmc-d0-socket-launch')
    assert launch['parent_sha256']==supply['sha256']
    stage=read('emmc-d0-data-pullup')
    assert stage['parent_sha256']==launch['candidate']['sha256']
    stage=stage['candidate']
    projection=read('emmc-data-plane-impact')
    assert projection['base_sha256']==checkpoint['sha256'] and projection['sha256']==stage['sha256']
    assert all(row['increase_mm2']<1e-6 for record in projection['records'] for row in record['projection'])
    verify_preservation(load(checkpoint),load(stage),replaced_copper=set(pivot['replaced'])|{moved['retired']})
    base_drc=json.loads(((root/checkpoint['board']).parent/'drc.json').read_text())
    current_drc=json.loads(((root/stage['board']).parent/'drc.json').read_text())
    assert not introduced(base_drc,current_drc)
    additional_pairs.extend([['L405.2','R8006.1'],['C8002.1','R8006.2'],['R8001.1','R8006.2'],['R8001.2','U8001.A3']])
    checkpoint=dict(stage,parent_sha256=checkpoint['sha256'])
if ca1:
    routed=read('ddr-command-in3-cu-compact-broadside')
    assert routed['parent_sha256']==checkpoint['sha256'] and len(routed['routes'])==1
    stage=read('ddr-command-ca1-returns')
    assert stage['parent_sha256']==routed['sha256']
    assert len(stage['terminal_results'])==2 and all(t['accepted'] for t in stage['terminal_results'])
    checks=read('ddr-command-ca1-returns-reference')
    assert checks['sha256']==stage['sha256'] and not checks['rows'][0]['projected_near_parallel_mm']
    assert all(t['nearest_common_gnd_mm']<0.75 for t in checks['rows'][0]['via_returns'])
    projection=read('ddr-ca1-plane-impact')
    assert projection['base_sha256']==checkpoint['sha256'] and projection['sha256']==stage['sha256']
    assert all(row['increase_mm2']<1e-6 for record in projection['records'] for row in record['projection'])
    verify_preservation(load(checkpoint),load(stage))
    additional_pairs.append(routed['routes'][0]['pair'])
    checkpoint=dict(stage,parent_sha256=checkpoint['sha256'])
board = load(checkpoint)
if clock_return:
    ground=board.FindFootprintByReference('U4').FindPadByNumber('69')
    ids={q.m_Uuid.AsString() for q in board.GetConnectivity().GetConnectedItems(ground)}
    assert set(vias)<=ids
    transferred=[v for v in board.GetTracks() if v.m_Uuid.AsString() in vias]
    assert all(v.GetNetname()=='GND' and v.GetDrillValue()==200000 and v.GetWidth(p.F_Cu)==450000 for v in transferred)

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
if wide_trunks:replaced.update(wide_replaced)
if vddq_trunk:replaced.update(vddq_replaced)
if vdd1_trunk:replaced.update(vdd1_replaced)
if radio_wake:replaced.update(radio_replaced)
if pin40:replaced.update(read('phy-pin40-integrated')['preservation']['explicitly_replaced_copper'])
if supply40:replaced.update(read('phy-pin40-5v-clearance')['change']['preservation']['explicitly_replaced_copper'])
if coincident:replaced.update(read('coincident-track-cleanup')['equivalent_retained_segments'])
if hanrun:replaced.update(read('hanrun-hole-stagger')['preservation']['explicitly_replaced_copper'])
if analog_1v8:replaced.update(read("usb-analog-1v8-c1682-restored")["result"][0]["preservation"]["explicitly_replaced_copper"])
if memory_local:replaced.update(replaced_memory)
if mux_enable:replaced.update(mux_replaced)
if lcd_cs:replaced.update(cs_ground_replaced)
if cpu_enable:replaced.update(en_replaced)
if spi0_pullup:replaced.update(local_replaced)
if sda_complete:replaced.update(read('exp-sda-soc-launch')['candidate']['preservation']['explicitly_replaced_copper'])
if sda_land:replaced.update(read('exp-sda-dual-land')['candidate']['preservation']['explicitly_replaced_copper'])
if dq0_reference:replaced.update(read('lpddr-dq0-reference')['preservation']['explicitly_replaced_copper'])
if pwron_filter:replaced.update(read('pmic-pwron-rear-filter')['preservation']['explicitly_replaced_copper'])
if ab4:replaced.update(ab4_retired)
if cap_return:replaced.update(carried)
if emmc_data:replaced.update(set(pivot['replaced'])|{moved['retired']})
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
historical_assertions=len(pairs)
if exp_clock:
    pairs=list(dict.fromkeys(tuple(sorted(pair)) for pair in pairs))
for a,z in pairs:
    assert membership[a] & membership[z], (a,z)
with tempfile.TemporaryDirectory() as tmp:
    result = Path(tmp)/'drc.json'
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(result),str(path)],check=True,capture_output=True)
    report=json.loads(result.read_text())
delta = introduced(json.loads((basepath.parent/'drc.json').read_text()),report)
assert not delta, delta
output = dict(board=checkpoint['board'],sha256=checkpoint['sha256'],parent_sha256=base['sha256'],verified_pairs=pairs,preservation=preservation,open_nets=unresolved,remaining_minimum_joins=sum(len(g)-1 for g in unresolved.values()),new_drc=delta,drc_counts=Counter(v['type'] for v in report['violations']),assembly_ready=False)
if exp_clock:
    output['pair_assertions_before_deduplication']=historical_assertions
if clock_return:
    # The connectivity inventory is checked against layout-storage-io, while
    # the immediate physical predecessor is the preceding accepted PCB.
    output['cumulative_audit_base_sha256']=base['sha256']
    output['parent_sha256']=read('usb-analog-1v8-c1682-restored')['parent_sha256'] if analog_1v8 else checkpoint['parent_sha256']
    if analog_1v8: output['previous_adopted_sha256']=analog_parent
    if emmc_adjacent: output['parent_sha256']=output['previous_adopted_sha256']=checkpoint['parent_sha256']
(root/('layout-command-ca1.json' if ca1 else 'layout-emmc-data-power.json' if emmc_data else 'layout-memory-n12-neighbors.json' if n12_near else 'layout-memory-n12.json' if n12_supply else 'layout-memory-zq-supply.json' if zq_supply else 'layout-memory-trunk-widths.json' if wide_trunks else 'layout-lpddr-vddq-source.json' if vddq_trunk else 'layout-lpddr-vdd1-source.json' if vdd1_trunk else 'layout-lpddr-vdd1-bank.json' if vdd1_bank else 'layout-radio-returns.json' if radio_returns else 'layout-radio-host-wake.json' if radio_wake else 'layout-gpu-cap-bank.json' if gpu_bank else 'layout-memory-cap-return.json' if cap_return else 'layout-memory-bank-rear-taps.json' if bank_rear else 'layout-memory-ab4-bank.json' if ab4_bank else 'layout-memory-ab4-bypass.json' if ab4 else 'layout-ground-land-offsets.json' if offset_ground else 'layout-memory-ground-neighbors.json' if memory_ground else 'layout-soc-ground-neighbors.json' if soc_ground else 'layout-soc-core-neighbors.json' if core_neighbors else 'layout-usb-direction-complete.json' if mux_dir else 'layout-memory-bank-c1665.json' if memory_local else 'layout-emmc-perimeter-supply.json' if emmc_perimeter else 'layout-emmc-adjacent-supply.json' if emmc_adjacent else 'layout-usb-analog-1v8.json' if analog_1v8 else 'layout-usb-analog-0v9.json' if analog_0v9 else 'layout-usb-enable-trunk.json' if mux_enable else 'layout-lcd-select-trunk.json' if lcd_cs else 'layout-lcd-clock-trunk.json' if lcd_clock else 'layout-cpu-enable-bias.json' if cpu_enable else 'layout-exp-spi0-pullup.json' if spi0_pullup else 'layout-exp-sda-complete.json' if sda_complete else 'layout-exp-sda-land.json' if sda_land else 'layout-wifi-io-pullup-bank.json' if wifi_io_bank else 'layout-exp-data-pullup.json' if exp_data else 'layout-exp-clock-pullup.json' if exp_clock else 'layout-lpddr-dq0-reference.json' if dq0_reference else 'layout-lpddr-clock-return.json' if clock_return else 'layout-pmic-pwron-filter.json' if pwron_filter else 'layout-soc-tx-series.json' if tx_series else 'layout-phy-source-series.json' if rx_series else 'layout-hanrun-hole-stagger.json' if hanrun else 'layout-coincident-cleanup.json' if coincident else 'layout-cpu-load-sense.json' if cpu_load else 'layout-power-probes.json' if power_probes else 'layout-wifi-sdio-bias.json' if wifi_bias else 'layout-aux-cap-banks.json' if aux_cap_banks else 'layout-ram-cap-bank.json' if ram_cap_bank else 'layout-ground-island-barrels.json' if island_barrels else 'layout-island-mesh.json' if island_mesh else 'layout-island-returns.json' if island_returns else 'layout-supply-islands.json' if supply_islands else 'layout-ground-islands.json' if ground_islands else 'layout-bank-feeds.json' if bank_feeds else 'layout-regulator-banks.json' if reg_banks else 'layout-storage-rail.json' if storage_rail else 'layout-emmc-pullups.json' if pullups else 'layout-usb-shell.json' if shell else 'layout-peripheral-supply-balls.json' if aux else 'layout-cap-bank.json' if cap_bank else 'layout-adjacent-supplies.json' if adjacent else 'layout-phy-pin40-powered.json' if supply40 else 'layout-phy-pin40.json' if pin40 else 'layout-outer-ground-mesh.json' if outer else 'layout-core-ground-mesh.json' if mesh else 'layout-all-ground-surface.json' if all_ground else 'layout-phy-full-feed.json' if full_feed else 'layout-opposite-bypass.json' if opposite else 'layout-package-local.json' if local_vias else 'layout-package-returns.json' if packages else 'layout-ground-bends.json' if ground_bends else 'layout-peripheral-returns.json' if peripheral else 'layout-regulator-joint.json')).write_text(json.dumps(output,indent=2)+'\n')
print(len(pairs),len(unresolved),output['remaining_minimum_joins'],output['drc_counts'],flush=True)
os._exit(0)
