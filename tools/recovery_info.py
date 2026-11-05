#!/usr/bin/env python3
"""Validate a completed full-flash backup without displaying its contents."""
import hashlib
import json
from pathlib import Path
p=Path('results/recovery/original-flash.bin')
if p.stat().st_size != 16*1024*1024:
    raise SystemExit('Backup is not the expected complete 16 MiB image')
report={'filename':p.name,'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
        'chip':'ESP32-P4','revision':'3.1','uart_serial':'5B90185921',
        'note':'Contains original device data. Keep private. No eFuse backup or changes.'}
Path('results/recovery/manifest.json').write_text(json.dumps(report,indent=2)+'\n')
p.chmod(0o600)
print(json.dumps(report,indent=2))
