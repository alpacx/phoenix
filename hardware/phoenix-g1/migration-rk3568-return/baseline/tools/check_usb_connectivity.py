#!/usr/bin/env python3
"""Check exported KiCad pin/net assignments, including intentionally open pins."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

root=Path(__file__).resolve().parents[1]/'review'
xml=ET.parse(root/'usb/usb-c-frontend.xml')
actual={}
for net in xml.findall('.//nets/net'):
    for pin in net.findall('node'):
        actual[pin.attrib['ref'],pin.attrib['pin']]=net.attrib['name']
expected=json.loads((root/'usb-c-frontend-expected.json').read_text())
errors=[]
for pin in expected:
    found=actual.get((pin['ref'],pin['pin']))
    if pin['net'] is not None and found != '/'+pin['net']:
        errors.append({'expected':pin,'actual':found})
    if pin['net'] is None and found and not found.startswith('unconnected-'):
        errors.append({'expected':pin,'actual':found})
report={'status':'FAIL' if errors else 'PASS', 'checked_pin_dispositions':len(expected),
        'errors':errors, 'scope':'CAD transcription only; NOT electrical validation, ERC approval or complete gateway verification.'}
(root/'usb/connectivity-check.json').write_text(json.dumps(report,indent=2)+'\n')
print(f"{report['status']}: {len(expected)} pin dispositions, {len(errors)} differences")
raise SystemExit(bool(errors))
