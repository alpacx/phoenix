"""Password administration, persistent account lockout and ephemeral sessions."""
import hashlib
import hmac
import math
from pathlib import Path
import secrets
import threading
import time
from .vault import Vault


class AdminAuth:
    def __init__(self, directory, clock=time.time):
        self.vault = Vault(directory)
        self.vault.path = Path(directory) / 'admin-password.json'
        self.clock, self.lock, self.sessions = clock, threading.RLock(), {}
        if not self.vault.path.exists():
            salt = secrets.token_hex(16)
            self.vault.save({'salt': salt, 'hash': self.derive('phoenix', salt),
                             'must_change': True, 'failures': 0, 'locked_until': 0})

    @staticmethod
    def derive(password, salt):
        return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

    def key(self, session):
        if not isinstance(session, str) or len(session) > 128:
            return ''
        return hashlib.sha256(session.encode()).hexdigest()

    def session(self, session):
        now = self.clock()
        self.sessions = {k: v for k, v in self.sessions.items() if v['expires'] > now}
        return self.sessions.get(self.key(session))

    def issue(self, must_change):
        if len(self.sessions) >= 32:
            self.sessions.pop(next(iter(self.sessions)))
        session = secrets.token_urlsafe(32)
        self.sessions[self.key(session)] = {'expires': self.clock() + (600 if must_change else 3600),
                                           'must_change': must_change}
        return {'ok': True, 'session': session, 'must_change': must_change}

    def check_password(self, state, password):
        if state['locked_until'] > self.clock():
            return {'ok': False, 'error': 'login_locked', 'retry_after': math.ceil(state['locked_until'] - self.clock())}
        valid = (isinstance(password, str) and len(password.encode()) <= 512
                 and hmac.compare_digest(state['hash'], self.derive(password, state['salt'])))
        if not valid:
            state['failures'] += 1
            if state['failures'] >= 3:
                state['failures'] = 0
                state['locked_until'] = self.clock() + 300
            self.vault.save(state)
            return {'ok': False, 'error': 'login_locked' if state['locked_until'] > self.clock() else 'invalid_password',
                    'retry_after': max(0, math.ceil(state['locked_until'] - self.clock()))}
        state.update(failures=0, locked_until=0)
        self.vault.save(state)
        return None

    def call(self, action, args):
        with self.lock:
            state = self.vault.load()
            session = self.session(args.get('session', ''))
            if action == 'status':
                return {'password_login': True, 'authenticated': bool(session),
                        'must_change': bool(session and session['must_change'])}
            if action == 'check':
                return {'ok': bool(session and not session['must_change'])}
            if action == 'logout':
                self.sessions.pop(self.key(args.get('session', '')), None)
                return {'ok': True}
            if action == 'login':
                error = self.check_password(state, args.get('password'))
                return error or self.issue(state['must_change'])
            if action == 'password':
                if not session:
                    return {'ok': False, 'error': 'authentication_required'}
                password = args.get('new_password')
                if not isinstance(password, str) or not 12 <= len(password) <= 128 or password == 'phoenix':
                    return {'ok': False, 'error': 'password_too_short'}
                error = self.check_password(state, args.get('current_password'))
                if error:
                    return error
                if hmac.compare_digest(state['hash'], self.derive(password, state['salt'])):
                    return {'ok': False, 'error': 'password_unchanged'}
                salt = secrets.token_hex(16)
                self.vault.save({'salt': salt, 'hash': self.derive(password, salt),
                                 'must_change': False, 'failures': 0, 'locked_until': 0})
                self.sessions.clear()
                return self.issue(False)
            raise ValueError('unknown_auth_action')
