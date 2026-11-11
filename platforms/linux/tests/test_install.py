import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from phoenix_linux.install import install
from phoenix_linux.package import build


class InstallTests(unittest.TestCase):
    def test_target_guard_and_first_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / 'target'
            (root / 'proc/device-tree').mkdir(parents=True)
            (root / 'proc/device-tree/model').write_text('Test target\0')
            bundle, config = base / 'bundle.zip', base / 'target.json'
            build(bundle)
            config.write_text(json.dumps({'expected_model': 'Wrong'}))
            with self.assertRaises(ValueError):
                install(bundle, config, root=root)
            self.assertFalse((root / 'opt').exists())
            config.write_text(json.dumps({'expected_model': 'Test target'}))
            install(bundle, config, root=root)
            self.assertEqual((root / 'opt/phoenix').resolve().name, 'factory')
            self.assertTrue((root / 'etc/systemd/system/phoenix.service').exists())
            # Verify bootstrap imports from its deployed layout, independently of app.
            source = root / 'opt/phoenix-bootstrap/platforms/linux/service'
            subprocess.run(['python3', '-c', 'import phoenix_linux.updates'],
                           env={'PATH': __import__('os').environ['PATH'], 'PYTHONPATH': str(source),
                                'PYTHONDONTWRITEBYTECODE': '1'}, check=True)
            with self.assertRaises(ValueError):
                install(bundle, config, root=root)
