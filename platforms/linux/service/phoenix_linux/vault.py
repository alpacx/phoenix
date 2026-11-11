"""Private local file for VPN credentials; never returned by the API."""
import json
import os
import tempfile
from pathlib import Path


class Vault:
    def __init__(self, directory):
        self.path = Path(directory) / 'vpn-private.json'

    def load(self):
        if not self.path.exists():
            return {}
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as stream:
            st = os.fstat(stream.fileno())
            if st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise ValueError('private_file_permissions')
            return json.load(stream)

    def save(self, settings):
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.vpn-')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(settings, stream, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)
