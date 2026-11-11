import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from phoenix_linux.controller import Controller
from phoenix_linux.runtime import Runtime
from test_policy import NAMES
from test_runtime import FakeRunner

ROOT = Path(__file__).resolve().parents[3]


class ContractTests(unittest.TestCase):
    def test_shared_ui_fields_exist_in_linux_and_esp32(self):
        class StatusRunner(FakeRunner):
            def __call__(self, argv, **kwargs):
                if argv[:3] == ['ip','-j','address']:
                    return subprocess.CompletedProcess(argv,0,'[]')
                if argv[:3] == ['nft','-j','list']:
                    return subprocess.CompletedProcess(argv,0,'{"nftables":[]}')
                return super().__call__(argv,**kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            controller = Controller(tmp, [], Runtime(NAMES,StatusRunner()))
            original = Path.read_text
            def read(path, *args, **kwargs):
                if str(path) == '/proc/meminfo':
                    return 'MemAvailable: 1000 kB\n'
                if str(path) == '/proc/uptime':
                    return '100.00 0.00\n'
                return original(path,*args,**kwargs)
            with patch.object(Path,'read_text',read):
                status = controller.runtime.status()
            vpn = controller.vpn_status()
        script = (ROOT/'shared/web/app.js').read_text()
        update = script[script.index('function update(s,v)'):script.index('async function loadCapabilities')]
        status_fields = set(re.findall(r'\bs\.([a-z_]+)',update))
        vpn_fields = set(re.findall(r'\bv\.([a-z_]+)',update))
        self.assertFalse(status_fields - status.keys())
        self.assertFalse(vpn_fields - vpn.keys())
        esp = '\n'.join(p.read_text() for p in (ROOT/'platforms/esp32/main').iterdir() if p.suffix in ('.inc','.c'))
        esp = esp.replace('\\"', '"')
        # Explicit optional fields are Linux-only capability refinements.
        optional = {'malformed_counter_available'}
        for field in status_fields - optional:
            self.assertIn('"'+field+'"',esp)
        for field in vpn_fields:
            self.assertIn('"'+field+'"',esp)
