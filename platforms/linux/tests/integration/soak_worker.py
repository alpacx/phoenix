"""Persistent controller for local Docker endurance. Secrets enter via stdin."""
import gc
import json
from pathlib import Path
import sys
import tempfile
import time
from phoenix_linux.controller import Controller
from phoenix_linux.runtime import Runtime, Runner

if not Path('/.dockerenv').exists():
    raise SystemExit('Container only')
setup=json.loads(sys.stdin.readline())
with tempfile.TemporaryDirectory() as tmp:
    runtime=Runtime(setup['names'],Runner())
    controller=Controller(tmp,[],runtime)
    for line in sys.stdin:
        action=json.loads(line)['action']
        try:
            if action=='connect':
                controller.command({'action':'wireguard','profile':setup['profile']})
                deadline=time.monotonic()+5
                while not runtime.handshake() and time.monotonic()<deadline:
                    time.sleep(.1)
                assert runtime.handshake()
                controller.tick()
            elif action=='loss':
                runtime.run(['ip','link','delete','phwg0'])
                controller.tick()
            else:
                controller.command({'action':action})
            gc.collect()
            fields=dict((row.split(':',1)[0],row.split(':',1)[1].strip()) for row in Path('/proc/self/status').read_text().splitlines() if ':' in row)
            print(json.dumps({'mode':runtime.mode,'rss_kib':int(fields['VmRSS'].split()[0]),'fds':len(list(Path('/proc/self/fd').iterdir()))}),flush=True)
        except Exception:
            print(json.dumps({'error':'soak_operation_failed','action':action}),flush=True)
            break
    controller.shutdown()
