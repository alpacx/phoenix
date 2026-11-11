#!/usr/bin/env python3
"""Regenerate and check the partial PCB, restoring prior outputs on failure."""
import json
import subprocess
import sys
from pathlib import Path
from transactional_hardware_build import preserve_outputs

R = Path(__file__).resolve().parents[1]
T, M = R/'tools', R/'migration-rk3562'
PY = '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9'
CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'


def script(name, *args):
    subprocess.run([PY, str(T/name), *map(str, args)], check=True)


def drc(board, report, require_no_warnings=False):
    subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '-o', str(report), str(board)], check=True)
    findings = json.loads(report.read_text())['violations']
    rejected = findings if require_no_warnings else [a for a in findings if a['severity'] == 'error']
    assert not rejected, 'Candidate DRC failed: '+str(rejected)


def main():
    # Run this build with no concurrent editors of these generated directories.
    with preserve_outputs([M/'review', M/'kicad/pcb', M/'kicad/floorplan']):
        stages = [[], ['--controls'], ['--auxiliary'], ['--power-sense'], ['--aon'], ['--returns']]
        script('build_rk3562_floorplan.py')
        drc(M/'kicad/floorplan/phoenix-g1-floorplan.kicad_pcb', M/'review/floorplan-assembly-drc.json')
        for args in stages:
            if args == ['--auxiliary']:
                script('place_rk3562_usb_thresholds.py')
            script('route_rk3562_usb_sense.py', *args)
            if not args:
                drc(M/'kicad/pcb/phoenix-g1.kicad_pcb', M/'review/pcb-early-drc.json')
        board = M/'kicad/pcb/phoenix-g1.kicad_pcb'
        candidate = M/'kicad/pcb/wifi-candidate.kicad_pcb'
        script('route_rk3562_wifi_converter.py', '--input', board, '--output', candidate,
               '--report', M/'review/wifi-converter-routing.json')
        candidate.replace(board)
        script('route_rk3562_wifi_supply.py', '--input', board, '--output', candidate,
               '--report', M/'review/wifi-input-supply-routing.json')
        candidate.replace(board)
        for tool, report in [('route_rk3562_wifi_output.py', 'wifi-output-supply-routing.json'),
                             ('route_rk3562_wifi_module_supply.py', 'wifi-module-supply-routing.json'),
                             ('route_rk3562_wifi_module_ground.py', 'wifi-module-ground-routing.json'),
                             ('route_rk3562_wifi_module_buck.py', 'wifi-module-buck-routing.json'),
                             ('route_rk3562_wifi_lpo.py', 'wifi-lpo-routing.json')]:
            script(tool, '--input', board, '--output', candidate, '--report', M/'review'/report)
            candidate.replace(board)
        drc(board, M/'review/pcb-drc.json', require_no_warnings=True)
        script('check_rk3562_pcb.py')
        script('audit_rk3562_usb_returns.py', '--require-ground', '--require-source', '--require-raw',
               '--require-guard', '--require-input', '--require-bypass', '--require-aon')
        script('audit_rk3562_courtyard_envelope.py', '--require-enclosure')
        script('audit_rk3562_wifi_converter.py', '--require-local', '--require-module-supply', '--require-module-ground', '--require-module-buck', '--require-lpo')
        script('audit_rk3562_usb_power.py')
        subprocess.run([sys.executable, str(T/'check_rk3562_release.py')], check=True)
    print('Partial USB and Wi-Fi converter layout checked. Full routing and qualification remain unresolved.')


if __name__ == '__main__':
    main()
