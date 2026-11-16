"""Fault injection on disposable files; this does not test KiCad routing."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import rebuild_display_controls as rebuild

class DisplayRollbackTest(unittest.TestCase):
    def test_mid_build_failure_restores_old_and_removes_new_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);pcb=root/'pcb';pcb.mkdir()
            baseline=pcb/'five-volt-testpoint.kicad_pcb';baseline.write_bytes(b'fixture baseline')
            baseline.with_suffix('.json').write_text(json.dumps({
                'status':'FIVE_VOLT_TESTPOINT_CONNECTED',
                'sha256':hashlib.sha256(baseline.read_bytes()).hexdigest()}))
            old=pcb/'display-led-feed.json';old.write_bytes(b'previous accepted report')
            checkpoint=root/'working-candidate.json';checkpoint.write_bytes(b'previous checkpoint')
            new=pcb/'display-led-feed.kicad_pcb'
            def fail(*args):
                old.write_bytes(b'partial report')
                checkpoint.write_bytes(b'partial checkpoint')
                new.write_bytes(b'partial board')
                raise RuntimeError('injected failure')
            with patch.object(rebuild,'D',root),patch.object(rebuild,'EXTRA',[checkpoint]),patch.object(rebuild,'run',fail):
                with self.assertRaisesRegex(RuntimeError,'injected failure'):
                    rebuild.main()
            self.assertEqual(old.read_bytes(),b'previous accepted report')
            self.assertEqual(checkpoint.read_bytes(),b'previous checkpoint')
            self.assertFalse(new.exists())
            self.assertEqual(baseline.read_bytes(),b'fixture baseline')

if __name__=='__main__':unittest.main()
