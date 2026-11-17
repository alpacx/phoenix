#!/usr/bin/env python3
"""Rebuild the display and Ethernet local copper checkpoint, rolling back all generated files on failure.

Run with KiCad's Python. No firmware, fabrication exports or orders.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
D = TOOLS.parent / 'migration-rk3562/experiments/pmic-ldo-inputs'
STAGES = [
    ('display-led-feed', 'route_display_led_feed.py', 'DISPLAY_LED_FEED_CONNECTED'),
    ('display-enable', 'route_display_enable.py', 'DISPLAY_ENABLE_CONNECTED'),
    ('display-buffer-bypass', 'route_display_buffer_bypass.py', 'DISPLAY_BUFFER_BYPASS_CONNECTED'),
    ('display-buffer-feed', 'route_display_buffer_feed.py', 'DISPLAY_BUFFER_FEED_CONNECTED'),
    ('display-input-pulls', 'route_display_input_pulls.py', 'DISPLAY_INPUT_PULLS_CONNECTED'),
    ('display-input-returns', 'route_display_input_returns.py', 'DISPLAY_INPUT_RETURNS_CONNECTED'),
    ('display-reservoir', 'route_display_reservoir.py', 'DISPLAY_RESERVOIR_CONNECTED'),
    ('display-io-bleed', 'route_display_io_bleed.py', 'DISPLAY_IO_BLEED_CONNECTED'),
    ('display-backlight-control', 'route_display_backlight_control.py', 'DISPLAY_BACKLIGHT_CONTROL_CONNECTED'),
    ('ethernet-reset-passives', 'route_ethernet_reset_passives.py', 'ETHERNET_RESET_PASSIVES_CONNECTED'),
    ('ethernet-strap-grounds', 'route_ethernet_strap_grounds.py', 'ETHERNET_STRAP_GROUNDS_CONNECTED'),
    ('ethernet-center-tap', 'route_ethernet_center_tap.py', 'ETHERNET_CENTER_TAP_CONNECTED'),
    ('ethernet-bias-grounds', 'route_ethernet_bias_grounds.py', 'ETHERNET_BIAS_GROUNDS_CONNECTED'),
    ('ethernet-clock-placement', 'route_ethernet_clock_placement.py', 'ETHERNET_CLOCK_PLACEMENT_CONNECTED'),
    ('ethernet-clock-grounds', 'route_ethernet_clock_grounds.py', 'ETHERNET_CLOCK_GROUNDS_CONNECTED'),
    ('ethernet-clock-pins', 'route_ethernet_clock_pins.py', 'ETHERNET_CLOCK_PINS_CONNECTED'),
    ('ethernet-cap-grounds', 'route_ethernet_cap_grounds.py', 'ETHERNET_CAP_GROUNDS_CONNECTED'),
    ('ethernet-bypass-local', 'route_ethernet_bypass_local.py', 'ETHERNET_BYPASS_LOCAL_CONNECTED'),
    ('ethernet-avdd33-bypass', 'route_ethernet_avdd33_bypass.py', 'ETHERNET_AVDD33_BYPASS_CONNECTED'),
    ('ethernet-io-power-link', 'route_ethernet_io_power_link.py', 'ETHERNET_IO_POWER_LINK_CONNECTED'),
    ('ethernet-avdd10-escape', 'route_ethernet_avdd10_escape.py', 'ETHERNET_AVDD10_ESCAPE_CONNECTED'),
    ('ethernet-io-bypass-escape', 'route_ethernet_io_bypass_escape.py', 'ETHERNET_IO_BYPASS_ESCAPE_CONNECTED'),
    ('ethernet-dvdd33-bypass', 'route_ethernet_dvdd33_bypass.py', 'ETHERNET_DVDD33_BYPASS_CONNECTED'),
]
EXTRA = [D/'working-candidate.json'] + [D/'pcb'/name for name in (
    'final-audit.json', 'connectivity-inventory.json', 'display-integration-audit.json',
    'display-routing-metrics.json','mount-component-screen.json','phy-supply-placement.json')]

def generated_paths():
    paths = set(EXTRA)
    for stem, _, _ in STAGES:
        paths.update((D/'pcb').glob(stem+'*'))
    return paths

def run(name, *args):
    result = subprocess.run([sys.executable, str(TOOLS/name), *map(str,args)],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(name+' failed:\n'+(result.stdout+result.stderr)[-10000:])


def main():
    baseline=D/'pcb/five-volt-testpoint.kicad_pcb'
    proof=json.loads(baseline.with_suffix('.json').read_text())
    assert proof['status']=='FIVE_VOLT_TESTPOINT_CONNECTED'
    assert hashlib.sha256(baseline.read_bytes()).hexdigest()==proof['sha256']
    previous={path for path in generated_paths() if path.exists()}
    with tempfile.TemporaryDirectory(prefix='phoenix-display-rollback-') as directory:
        backup=Path(directory)
        for path in previous:
            target=backup/path.relative_to(D)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
        try:
            for stem,script,status in STAGES:
                run(script)
                report=json.loads((D/'pcb'/f'{stem}.json').read_text())
                assert report['status']==status and not report['new_violations'],stem
                assert hashlib.sha256((D/'pcb'/f'{stem}.kicad_pcb').read_bytes()).hexdigest()==report['sha256'],stem
                print(stem+': accepted geometry and continuity',flush=True)
            run('audit_pmic_ldo_inputs.py')
            run('test_pmic_ldo_input_audit.py')
            run('test_phy_clock_power_clearance.py')
            run('audit_display_integration.py')
            run('report_display_routing.py')
            run('report_phy_supply_placement.py')
            run('audit_mount_component_reservations.py','--baseline',D/'pcb/ethernet-bias-grounds.kicad_pcb')
            assert not json.loads((D/'pcb/mount-component-screen.json').read_text())['introduced_conflicts']
            run('test_mount_component_reservations.py')
            run('inventory_stacked_connectivity.py','--checkpoint',D/'working-candidate.json')
        except BaseException:
            for path in generated_paths()-previous:
                if path.is_file():path.unlink()
            for path in previous:
                shutil.copy2(backup/path.relative_to(D),path)
            print('Previous generated checkpoint restored.',file=sys.stderr)
            raise
    print('Local copper checkpoint rebuilt and audited; electrical/production qualification remains open.')

if __name__=='__main__':
    main()
