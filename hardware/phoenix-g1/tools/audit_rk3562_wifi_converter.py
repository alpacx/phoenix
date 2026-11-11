#!/usr/bin/env python3
"""Check local U26 connectivity in saved copper, independently of route recipes."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import pcbnew as p

R = Path(__file__).resolve().parents[1]/'migration-rk3562'
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--board', type=Path, default=R/'kicad/pcb/phoenix-g1.kicad_pcb')
ap.add_argument('--report', type=Path, default=R/'review/wifi-converter-copper-audit.json')
ap.add_argument('--require-local', action='store_true')
ap.add_argument('--require-module-supply', action='store_true')
ap.add_argument('--require-module-ground', action='store_true')
ap.add_argument('--require-module-buck', action='store_true')
ap.add_argument('--require-vddio-bypass', action='store_true')
ap.add_argument('--require-lpo', action='store_true')
ap.add_argument('--require-lpo-bypass', action='store_true')
args = ap.parse_args()
b = p.LoadBoard(str(args.board)); b.BuildConnectivity()
conn = b.GetConnectivity()
pads = {(f.GetReference(), a.GetNumber()): a for f in b.GetFootprints() for a in f.Pads()}
expected = json.loads((R/'review/wifi-vbat-converter-expected.json').read_text())
assert all(pads[a['ref'], a['pin']].GetNetname() == a['net'] for a in expected)

def label(a):
    return a.GetParentFootprint().GetReference()+'.'+a.GetNumber()

def cluster(a):
    return {label(i) for i in conn.GetConnectedItems(a) if isinstance(i, p.PAD)} | {label(a)}

def front_cluster(a):
    queue, seen, found = [a], set(), set()
    while queue:
        q = queue.pop()
        uid = q.m_Uuid.AsString()
        if uid in seen:
            continue
        seen.add(uid)
        if isinstance(q, p.PAD):
            found.add(label(q))
        queue.extend(i for i in conn.GetConnectedPads(q) if i.IsOnLayer(p.F_Cu))
        queue.extend(i for i in conn.GetConnectedTracks(q) if i.GetClass() == 'PCB_TRACK' and i.GetLayer() == p.F_Cu)
    return found

nets = []
for name in sorted({a['net'] for a in expected}):
    local = sorted(a['ref']+'.'+a['pin'] for a in expected if a['net'] == name)
    start = pads[tuple(local[0].split('.'))]
    reached = cluster(start)
    nets.append({'net': name, 'local_endpoints': local,
                 'unreachable_local': sorted(set(local)-reached),
                 'connected': set(local) <= reached,
                 'unreachable_external': sorted(label(a) for a in pads.values() if a.GetNetname() == name and label(a) not in reached and label(a) not in local)})

ep = front_cluster(pads['U26', '17'])
required_ground = {'U26.6', 'U26.7', 'U26.8', 'U26.15', 'U26.16', 'C2201.2', 'C2204.2'}
front_power_pairs = [('C2201', '1', 'U26', '11'), ('C2202', '1', 'U26', '10'),
                     ('L2201', '1', 'U26', '1'), ('L2201', '2', 'C2204', '1')]
front_power = [{'from': ar+'.'+ap, 'to': zr+'.'+zp,
                'connected_on_front': zr+'.'+zp in front_cluster(pads[ar, ap])}
               for ar, ap, zr, zp in front_power_pairs]
source_ground = cluster(pads['U26', '17'])
ground_refs = [a['ref']+'.'+a['pin'] for a in expected if a['net'] == 'GND']
source_ground_ok = all(g in source_ground for g in ground_refs+['J1.A1', 'J1.A12', 'J1.B1', 'J1.B12'])
distances = []
for ref, pin in [('C2201', '11'), ('C2202', '10'), ('C2203', '9'), ('C2204', '14'), ('R2203', '5')]:
    a, z = pads[ref, '1'], pads['U26', pin]
    distances.append({'component': ref, 'target': 'U26.'+pin,
                      'pad_center_distance_mm': round(math.hypot(p.ToMM(a.GetPosition().x-z.GetPosition().x), p.ToMM(a.GetPosition().y-z.GetPosition().y)), 4),
                      'same_front_layer': a.IsOnLayer(p.F_Cu) and z.IsOnLayer(p.F_Cu)})

report = {
    'status': 'LOCAL COPPER CONTINUITY ONLY; BOARD STILL INCOMPLETE',
    'pcb_sha256': hashlib.sha256(args.board.read_bytes()).hexdigest(),
    'local_nets': nets, 'local_nets_complete': all(a['connected'] for a in nets),
    'agnd_pgnd_and_power_caps_direct_front_to_ep': required_ground <= ep,
    'missing_direct_front_ground': sorted(required_ground-ep),
    'front_power_connections': front_power,
    'local_grounds_continuous_to_usb_source': source_ground_ok,
    'usb_main_switch_to_wifi_converter': 'U15.5' in cluster(pads['U26', '10']),
    'power_good_to_system_enable': 'U17.13' in cluster(pads['U26', '4']),
    'output_to_ferrite': 'FB2001.1' in cluster(pads['C2204', '1']),
    'ferrite_to_module_and_bypass': {'U25.9', 'C2001.1', 'C2002.1'} <= cluster(pads['FB2001', '2']),
    'module_bypass_ground_to_usb': {'C2001.2', 'C2002.2'} <= source_ground,
    'unconnected_module_ground_pads': sorted(label(a) for a in pads.values() if a.GetParentFootprint().GetReference() == 'U25' and a.GetNetname() == 'GND' and label(a) not in source_ground),
    'module_buck_switch_connected': 'L2001.1' in cluster(pads['U25', '21']),
    'module_buck_output_connected': {'L2001.2', 'C2003.1'} <= cluster(pads['U25', '23']),
    'module_buck_cap_ground_to_usb': 'C2003.2' in source_ground,
    'module_buck_switch_back_only_no_vias': all(t.GetClass() == 'PCB_TRACK' and t.GetLayer() == p.B_Cu for t in b.GetTracks() if t.GetNetname() == 'WIFI_BUCK_SW'),
    'vddio_local_bypass_connected': {'C2004.1', 'C2005.1', 'C2006.1'} <= cluster(pads['U25', '22']),
    'vddio_bypass_ground_to_usb': {'C2004.2', 'C2005.2', 'C2006.2'} <= source_ground,
    'vddio_upstream_pmic_connected': 'U4.55' in cluster(pads['U25', '22']),
    'lpo_source_to_series_resistor': 'R2003.1' in cluster(pads['Y2001', '3']),
    'lpo_series_resistor_to_module': 'U25.24' in cluster(pads['R2003', '2']),
    'lpo_source_ground_to_usb': 'Y2001.2' in source_ground,
    'lpo_local_bypass_connected': {'Y2001.1', 'Y2001.4'} <= cluster(pads['C2007', '1']),
    'lpo_bypass_ground_to_usb': 'C2007.2' in source_ground,
    'lpo_local_feed_from_module_io': 'C2007.1' in cluster(pads['U25', '22']),
    'lpo_source_power_from_pmic': {'Y2001.1', 'Y2001.4'} <= cluster(pads['U4', '55']),
    'component_pad_distances': distances,
    'limitations': ['Continuity and center distances do not qualify loop inductance, stability, current or thermal limits.',
                    'Other main 5 V loads and signal paths remain outside this audit. VDDIO upstream continuity is reported separately from local bypass. Buck continuity does not qualify switching performance.',
                    'Three thermal vias are candidates; fill/plug, stencil and assembly process remain unqualified.'],
    'production_ready': False,
}
args.report.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k: v for k, v in report.items() if k != 'local_nets'}, indent=2))
if args.require_local:
    assert report['local_nets_complete'], 'Local U26 network incomplete'
    assert report['agnd_pgnd_and_power_caps_direct_front_to_ep'], 'Direct front ground missing'
    assert all(a['connected_on_front'] for a in front_power), 'Front power branch missing'
    assert source_ground_ok, 'Ground return does not reach USB source'
    assert report['power_good_to_system_enable'], 'System regulator enable is disconnected'

if args.require_local:
    assert report['usb_main_switch_to_wifi_converter'], 'Wi-Fi converter input disconnected from main USB switch'

if args.require_module_supply:
    assert report['output_to_ferrite'], 'Converter output disconnected from ferrite'
    assert report['ferrite_to_module_and_bypass'], 'Module or bypass supply disconnected'
    assert report['module_bypass_ground_to_usb'], 'Bypass ground does not reach USB source'

if args.require_module_ground:
    assert not report['unconnected_module_ground_pads'], 'Module ground pads disconnected'

if args.require_module_buck:
    assert report['module_buck_switch_connected'], 'Module switch-to-inductor disconnected'
    assert report['module_buck_output_connected'], 'Module buck output disconnected'
    assert report['module_buck_cap_ground_to_usb'], 'Module buck output-cap ground disconnected'
    assert report['module_buck_switch_back_only_no_vias'], 'Switch node must stay on back without vias'

if args.require_vddio_bypass:
    assert report['vddio_local_bypass_connected'], 'Local VDDIO bypass disconnected'
    assert report['vddio_bypass_ground_to_usb'], 'VDDIO bypass ground disconnected'

if args.require_lpo:
    assert report['lpo_source_to_series_resistor'], 'Clock source-to-resistor disconnected'
    assert report['lpo_series_resistor_to_module'], 'Clock resistor-to-module disconnected'
    assert report['lpo_source_ground_to_usb'], 'Clock source ground disconnected'

if args.require_lpo_bypass:
    assert report['lpo_local_bypass_connected'], 'Local oscillator bypass disconnected'
    assert report['lpo_bypass_ground_to_usb'], 'Oscillator bypass ground disconnected'
    assert report['lpo_local_feed_from_module_io'], 'Oscillator local IO feed disconnected'
