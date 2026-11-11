"""Eight-hour confirmed connection history in the private state database."""
import sqlite3
import time
from contextlib import closing


class History:
    def __init__(self, store, clock=time.time):
        self.path, self.clock = store.path, clock
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, connected_at INTEGER NOT NULL, country TEXT NOT NULL, server TEXT NOT NULL, server_id INTEGER NOT NULL)')

    def add_confirmed(self, country, server, server_id):
        now = int(self.clock())
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DELETE FROM history WHERE connected_at<=? OR connected_at>?', (now - 28800, now))
            db.execute('INSERT INTO history(connected_at,country,server,server_id) VALUES(?,?,?,?)', (now, country, server, server_id))

    def page(self, before=0):
        if type(before) is not int or before < 0:
            raise ValueError('invalid_cursor')
        now = int(self.clock())
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DELETE FROM history WHERE connected_at<=? OR connected_at>?', (now - 28800, now))
            rows = db.execute('SELECT id,connected_at,country,server,server_id FROM history WHERE (?=0 OR id<?) ORDER BY id DESC LIMIT 51', (before, before)).fetchall()
        entries = [dict(zip(('id', 'connected_at', 'country', 'server', 'server_id'), r)) for r in rows[:50]]
        return {'persistent': True, 'now': now, 'entries': entries, 'next_before': entries[-1]['id'] if len(rows) > 50 else 0}
