from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
from phoenix_linux.uploadcheck import acknowledged, run

class UploadTests(unittest.TestCase):
    def test_only_full_successful_requests_count(self):
        self.assertEqual(acknowledged(0, '1024 200',1024),1024)
        for code,out in [(28,'1024 200'),(0,'1024 413'),(0,'nan 200'),(0,'512 200'),(0,'1024 302')]:
            with self.assertRaises(ValueError): acknowledged(code,out,1024)

    def test_native_upload_is_bound_and_uses_only_synthetic_payload(self):
        commands=[]
        class Process:
            returncode=0
            def __init__(self,args,**kw):
                commands.append(args)
                self.size=Path(args[args.index('--upload-file')+1]).stat().st_size
            def communicate(self,timeout=None):
                time.sleep(.02)
                return (f'{self.size} 200'.encode(),None)
            def poll(self): return self.returncode
        with patch('phoenix_linux.uploadcheck.subprocess.Popen',Process):
            result=run('/usr/bin/curl','phwg0',threading.Event(),lambda:[50],duration=.15)
        self.assertGreater(result['upload_mbps'],0)
        self.assertEqual(result['upload_error'],'')
        self.assertTrue(all('if!phwg0' in c and '--noproxy' in c and '--request' in c for c in commands))
        self.assertTrue(all(not Path(c[c.index('--upload-file')+1]).exists() for c in commands))

    def test_cancelled_upload_does_not_report_speed(self):
        stop=threading.Event();stop.set()
        result=run('/usr/bin/curl','phwg0',stop,lambda:[50],duration=.1)
        self.assertIsNone(result['upload_mbps'])
