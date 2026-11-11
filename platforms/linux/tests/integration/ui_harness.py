"""Disposable Docker UI test target. Public test token, never real credentials."""
from pathlib import Path
from http.server import HTTPServer
import json
from phoenix_linux.controller import Controller
from phoenix_linux.runtime import Runtime, Runner
from phoenix_linux.server import handler, WEB
if not Path('/.dockerenv').exists():
    raise SystemExit('Container only')
runner=Runner()
for name in ('testap','testusb'):
    runner(['ip','link','add',name,'type','dummy'])
runtime=Runtime({'ap':'testap','usb':'testusb','uplink':'eth0','vpn':'phwg0'},runner)
controller=Controller('/tmp/ui-state',json.loads((WEB/'countries.json').read_text()),runtime)
HTTPServer(('0.0.0.0',18086),handler(controller,'a'*64)).serve_forever()
