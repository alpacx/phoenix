"""Small, allowlisted local control protocol; no shell/file/argv RPC methods.

The HTTP process is unprivileged. The root worker checks kernel peer UID and
validates requests again. Possession of the web UID authorizes admin commands,
not arbitrary execution. Payloads and exception strings are never logged.
"""
import base64
import json
import os
from pathlib import Path
import socket
import socketserver
import struct
import time
from .jsonutil import loads
from .controller import Unavailable
from .store import RevisionConflict

LIMIT = 28 * 1024 * 1024


def receive(stream):
    deadline = time.monotonic() + 20
    def exact(size):
        result = bytearray()
        while len(result) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError('rpc_read_deadline')
            stream.settimeout(remaining)
            data = stream.recv(min(65536, size - len(result)))
            if not data:
                raise ValueError('truncated_rpc')
            result.extend(data)
        return bytes(result)
    size = struct.unpack('!I', exact(4))[0]
    if not 0 < size <= LIMIT:
        raise ValueError('rpc_too_large')
    return loads(exact(size))


def send(stream, value):
    data = json.dumps(value, allow_nan=False).encode()
    if len(data) > LIMIT:
        raise ValueError('rpc_too_large')
    stream.sendall(struct.pack('!I', len(data)) + data)


class LocalAPI:
    def __init__(self, controller):
        self.controller = controller

    def call(self, method, args=None):
        c, args = self.controller, {} if args is None else args
        if not isinstance(args, dict):
            raise ValueError('invalid_rpc_arguments')
        if method == 'health':
            return {'ready': not c.closing, 'release_id': Path(__file__).resolve().parents[4].name}
        if method == 'capabilities':
            from .speedcheck import available
            return {'network_initialized': c.runtime is not None, 'speedtest': c.runtime is not None and available(),
                    'wifi_provisioning': c.station is not None, 'usb_provisioning': False,
                    'firmware_update': c.updates is not None,
                    'exit_ip_verification': c.runtime is not None, 'catalog_test': c.runtime is not None}
        if method == 'speedtest':
            return c.measurement.status()
        if method == 'speedtest_start':
            return c.start_speedtest()
        if method == 'speedtest_cancel':
            c.measurement.cancel()
            return {'accepted': True}
        if method == 'status':
            c.require_runtime()
            return c.runtime.status()
        if method == 'policy':
            return c.policy()
        if method == 'save_policy':
            if not c.lock.acquire(blocking=False):
                raise RevisionConflict('command_in_progress')
            try:
                return c.save_policy(args)
            finally:
                c.lock.release()
        if method == 'vpn':
            return c.vpn_status()
        if method == 'command':
            return c.submit(args)
        if method == 'history':
            return c.history.page(int(args.get('before', 0)))
        if method == 'preflight':
            from .preflight import inspect
            return inspect()
        if method == 'scan':
            if not c.station or (c.access_point and c.access_point.active and c.station.name == c.base_ap):
                raise Unavailable('scan_unavailable')
            return c.station.scan()
        if method == 'firmware':
            if not c.updates:
                raise Unavailable('updates_not_configured')
            return c.updates.status()
        if method == 'upload':
            if not c.updates:
                raise Unavailable('updates_not_configured')
            from .updates import MAX_UPLOAD
            data = base64.b64decode(args['data'], validate=True)
            if not 0 < len(data) <= MAX_UPLOAD:
                raise ValueError('update_too_large')
            if not c.lock.acquire(blocking=False):
                raise RevisionConflict('command_in_progress')
            try:
                if c.busy or c.closing or c.updating:
                    raise RevisionConflict('command_in_progress')
                value = c.updates.stage(data)
                c.updating = True
                c.want_connected = c.enabled = False
                c.retry_at = None
                c.timer.disconnected()
                c.runtime.block(c.policy())
                c.runtime.run(['systemctl', 'start', '--no-block', 'phoenix-update.service'])
                return value
            finally:
                c.lock.release()
        raise ValueError('unknown_rpc_method')


class ControlServer(socketserver.UnixStreamServer):
    def __init__(self, path, api, allowed_uid):
        self.api, self.allowed_uid = api, allowed_uid
        path = Path(path)
        # systemd owns the private directory. Refuse replacing non-socket files.
        if path.exists():
            import stat
            if path.is_symlink() or not stat.S_ISSOCK(path.stat().st_mode):
                raise ValueError('unsafe_control_socket')
            path.unlink()
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.settimeout(20)
                try:
                    _, uid, _ = struct.unpack('3i', self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid != self.server.allowed_uid:
                        return
                    request = receive(self.request)
                    if not isinstance(request, dict) or set(request) != {'method', 'args'}:
                        raise ValueError('invalid_rpc_request')
                    if not isinstance(request['method'], str) or not isinstance(request['args'], dict):
                        raise ValueError('invalid_rpc_request')
                    result = self.server.api.call(request['method'], request['args'])
                    send(self.request, {'result': result})
                except RevisionConflict:
                    send(self.request, {'error': 'conflict'})
                except Unavailable:
                    send(self.request, {'error': 'unavailable'})
                except Exception:
                    try:
                        send(self.request, {'error': 'invalid_or_failed_operation'})
                    except OSError:
                        pass
        super().__init__(str(path), Handler)
        path.chmod(0o660)


class RemoteAPI:
    def __init__(self, path):
        self.path = str(path)

    def call(self, method, args=None):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.settimeout(25)
            stream.connect(self.path)
            send(stream, {'method': method, 'args': args or {}})
            response = receive(stream)
        if response.get('error') == 'conflict':
            raise RevisionConflict('command_in_progress')
        if response.get('error') == 'unavailable':
            raise Unavailable('capability_unavailable')
        if 'error' in response:
            raise ValueError('invalid_or_failed_operation')
        return response['result']
