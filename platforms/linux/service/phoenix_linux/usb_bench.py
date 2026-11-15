"""Explicit, current-boot laboratory exception; never electrical certification."""
import json
from pathlib import Path
import re
import stat

PERMIT = Path('/run/phoenix-usb-bench.json')


def authorized(options):
    if options.get('bench_unmeasured_vbus') is not True:
        return False
    try:
        info = PERMIT.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            return False
        permit = json.loads(PERMIT.read_text())
        model = Path('/proc/device-tree/model').read_text().strip('\0\n')
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        status = Path('/proc/device-tree/vbus-typec/status').read_text().strip('\0\n')
        gpio = Path('/sys/kernel/debug/gpio').read_text()
        return (model == 'Radxa ROCK 4C+' and status == 'disabled'
                and permit == {'boot_id': boot, 'udc': options['udc'],
                               'acknowledge_unmeasured_vbus': True}
                and options['udc'] == 'fe800000.usb'
                and re.search(r'^\s*gpio-35\s+\([^\n]*\|phoenix-usb-source-o(?:ff)?\s*\)\s+out lo\s*$',
                              gpio, re.MULTILINE) is not None)
    except (OSError, ValueError, KeyError):
        return False
