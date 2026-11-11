"""Transactional desired-state storage; saving does NOT apply network settings.

Only validated, non-secret desired configuration belongs here. VPN key storage
and the privilege boundary for applying configuration are separate modules.
"""
from contextlib import closing
import json
import os
import sqlite3
from pathlib import Path


class RevisionConflict(Exception):
    pass


class ConfigStore:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink() or directory.stat().st_uid != os.getuid():
            raise ValueError('state_directory_must_be_owned_and_not_symlink')
        if directory.stat().st_mode & 0o077:
            raise ValueError('state_directory_must_be_private')
        self.path = directory / 'desired.sqlite3'
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        if self.path.stat().st_uid != os.getuid() or self.path.stat().st_mode & 0o077:
            raise ValueError('state_database_must_be_private')
        with closing(self._connect()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS config '
                       '(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, payload TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO config VALUES (1, 0, ?)',
                       (json.dumps({'schema_version': 1, 'direct': False}),))

    def _connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def load(self):
        with closing(self._connect()) as db, db:
            revision, payload = db.execute('SELECT revision,payload FROM config WHERE id=1').fetchone()
        return {'revision': revision, 'desired': json.loads(payload)}

    def save(self, expected_revision, desired, validate):
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('invalid_revision')
        # Reject NaN and unsupported objects before opening a write transaction.
        payload = json.dumps(desired, allow_nan=False)
        if len(payload.encode()) > 65536:
            raise ValueError('configuration_too_large')
        validate(json.loads(payload))
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            revision = db.execute('SELECT revision FROM config WHERE id=1').fetchone()[0]
            if revision != expected_revision:
                raise RevisionConflict('revision_conflict_reload')
            db.execute('UPDATE config SET revision=?,payload=? WHERE id=1',
                       (revision + 1, payload))
        return {'revision': revision + 1, 'desired': json.loads(payload)}
