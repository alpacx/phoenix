"""Engineering administration server, bound only to loopback; use SSH forwarding.

No automatic hardware discovery-to-configuration conversion. Network mode needs
an explicit target assignment file and a root Linux process.
"""
from contextlib import nullcontext
import argparse
import base64
import hmac
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import re
import secrets
import signal
import zipfile
import threading
from urllib.parse import urlsplit, parse_qs
from .controller import Controller, Unavailable
from .store import RevisionConflict
from .runtime import Runtime, Runner, NetworkError
from .preflight import inspect
from .lan import AccessPoint
from .station import Station

ROOT = Path(__file__).resolve().parents[4]
WEB = ROOT / 'shared/web'


from .jsonutil import loads as strict_json


def handler(controller, token):
    from .rpc import LocalAPI, RemoteAPI
    api = controller if isinstance(controller, RemoteAPI) else LocalAPI(controller)
    class Handler(BaseHTTPRequestHandler):
        server_version = 'Phoenix'

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass  # No request data, query strings or credentials in access logs.

        def send(self, code, value, content_type='application/json'):
            data = json.dumps(value).encode() if content_type == 'application/json' else value
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            if any(len(self.headers.get_all(name, [])) > 1 for name in ('Host', 'Origin', 'Authorization')):
                self.send(400, {'error': 'duplicate_security_header'})
                return False
            expected_host = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected_host:
                self.send(403, {'error': 'host_not_allowed'})
                return False
            origin = self.headers.get('Origin')
            if origin and origin != ('https://' if getattr(self.server, 'tls', False) else 'http://') + expected_host:
                self.send(403, {'error': 'origin_not_allowed'})
                return False
            auth = self.headers.get('Authorization', '')
            if not hmac.compare_digest(auth.encode(), ('Bearer ' + token).encode()):
                self.send(401, {'error': 'authentication_required'})
                return False
            return True

        def do_GET(self):
            path = urlsplit(self.path).path
            assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                      '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                      '/app.css': ('app.css', 'text/css; charset=utf-8'),
                      '/countries.json': ('countries.json', 'application/json; charset=utf-8')}
            if path == '/healthz':
                try:
                    health = api.call('health')
                    health['ready'] = bool(health.get('ready') and health.get('release_id') == ROOT.name)
                    return self.send(200, health)
                except Exception:
                    return self.send(503, {'ready': False})
            if path in assets:
                name, mime = assets[path]
                return self.send(200, (WEB / name).read_bytes(), mime)
            if not self.authorized():
                return
            try:
                with nullcontext():
                    methods = {'/api/v1/speedtest': 'speedtest', '/api/v1/capabilities': 'capabilities', '/api/v1/wifi/scan': 'scan',
                               '/api/v1/firmware': 'firmware', '/api/v1/preflight': 'preflight',
                               '/api/v1/status': 'status', '/api/v1/policy': 'policy', '/api/v1/vpn': 'vpn'}
                    if path in methods:
                        value = api.call(methods[path])
                    elif path == '/api/v1/vpn/history':
                        before = int(parse_qs(urlsplit(self.path).query).get('before', ['0'])[0])
                        value = api.call('history', {'before': before})
                    else:
                        return self.send(404, {'error': 'not_found'})
                self.send(200, value)
            except Unavailable:
                self.send(503, {'error': 'target_network_not_initialized'})
            except (ValueError, KeyError, TypeError):
                self.send(400, {'error': 'invalid_request'})
            except Exception:
                self.send(500, {'error': 'operation_failed'})

        def do_POST(self):
            if not self.authorized():
                return
            try:
                if urlsplit(self.path).path == '/api/v1/firmware' and self.headers.get_content_type() == 'application/octet-stream':
                    lengths = self.headers.get_all('Content-Length', [])
                    if self.headers.get('Transfer-Encoding') or len(lengths) != 1 or not lengths[0].isdigit():
                        return self.send(411, {'error': 'content_length_required'})
                    from .updates import MAX_UPLOAD
                    size = int(lengths[0])
                    if not 0 < size <= MAX_UPLOAD:
                        return self.send(413, {'error': 'update_too_large'})
                    data = self.rfile.read(size)
                    if len(data) != size:
                        raise ValueError('incomplete_update')
                    value = api.call('upload', {'data': base64.b64encode(data).decode()})
                    return self.send(202, value)
                if self.headers.get('Transfer-Encoding') or self.headers.get_content_type() != 'application/json':
                    return self.send(415, {'error': 'json_required'})
                lengths = self.headers.get_all('Content-Length', [])
                if len(lengths) != 1 or not lengths[0].isdigit():
                    return self.send(411, {'error': 'content_length_required'})
                length = int(lengths[0])
                if not 0 < length <= 16384:
                    return self.send(413, {'error': 'body_too_large'})
                body = strict_json(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('object_required')
                path = urlsplit(self.path).path
                if path == '/api/v1/speedtest':
                    if set(body) != {'action'} or body['action'] not in ('start', 'cancel'):
                        raise ValueError('invalid_speedtest_action')
                    value = api.call('speedtest_' + body['action'])
                    return self.send(202, value)
                elif path == '/api/v1/policy':
                    value = api.call('save_policy', body)
                elif path in ('/api/v1/wifi', '/api/v1/uplink'):
                    body['action'] = path.rsplit('/', 1)[1]
                    value = api.call('command', body)
                    return self.send(202, value)
                elif path == '/api/v1/vpn':
                    value = api.call('command', body)
                    return self.send(202, value)
                else:
                    return self.send(501, {'error': 'endpoint_not_implemented'})
                self.send(200, value)
            except RevisionConflict:
                self.send(409, {'error': 'revision_conflict_reload'})
            except Unavailable:
                self.send(503, {'error': 'capability_unavailable'})
            except (ValueError, KeyError, TypeError, UnicodeError, zipfile.BadZipFile):
                self.send(400, {'error': 'invalid_configuration'})
            except Exception:
                self.send(500, {'error': 'operation_failed'})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--port', type=int, default=8085)
    parser.add_argument('--target-config', help='Enables network mutations on the identified Linux target')
    parser.add_argument('--worker-socket')
    parser.add_argument('--web-user', default='phoenix-web')
    args = parser.parse_args()
    if args.worker_socket and not args.target_config:
        raise SystemExit('Worker requires an identified target')
    runtime = None
    if args.target_config:
        config = strict_json(Path(args.target_config).read_text())
        model = Path('/proc/device-tree/model').read_text().strip('\0\n')
        if not config.get('expected_model') or config['expected_model'] != model:
            raise SystemExit('Target model mismatch')
        runtime = Runtime(config['interfaces'], Runner())
        # Establish a barrier even if persistent configuration is corrupt.
        runtime.block({'revision': 0, 'default_allow': False, 'rules': [], 'forwards': []})
    controller = Controller(args.state_dir, json.loads((WEB / 'countries.json').read_text()), runtime)
    stop = threading.Event()
    ap = None
    server = None
    def terminate(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        path = Path(args.state_dir) / 'admin-token'
        if not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w') as stream:
                stream.write(secrets.token_hex(32))
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as stream:
            st = os.fstat(stream.fileno())
            if st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise SystemExit('Admin token permissions invalid')
            token = stream.read().strip()
        if not re.fullmatch('[0-9a-f]{64}', token):
            raise SystemExit('Admin token format invalid')
        if args.worker_socket:
            import pwd
            from .rpc import ControlServer, LocalAPI
            server = ControlServer(args.worker_socket, LocalAPI(controller), pwd.getpwnam(args.web_user).pw_uid)
        else:
            server = HTTPServer(('127.0.0.1', args.port), handler(controller, token))
        if runtime:
            runtime.disconnect(controller.policy())
            for priority in ('17690', '17691', '17710', '17711'):
                runtime.run(['ip', 'rule', 'del', 'priority', priority], optional=True)
            if config.get('updates_config'):
                from .updates import from_config
                if config['updates_config'] != '/etc/phoenix/updates.json':
                    raise ValueError('unexpected_updates_config_path')
                controller.updates = from_config(config['updates_config'])
            if config.get('station_interface'):
                station_name = config['station_interface']
                if station_name in (runtime.names['uplink'], runtime.names['usb'], runtime.names['vpn']):
                    raise ValueError('station_interface_role_conflict')
                controller.station = Station(station_name, Path(args.state_dir) / 'wifi', runtime.run, '/run/NetworkManager/system-connections')
                controller.station.prepare_startup(bool(config.get('access_point')) and station_name == controller.base_ap)
            if config.get('access_point'):
                settings = config['access_point']
                fd = os.open(settings['password_file'], os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd) as stream:
                    st = os.fstat(stream.fileno())
                    if st.st_uid != os.getuid() or st.st_mode & 0o077:
                        raise ValueError('wifi_secret_permissions')
                    password = stream.read(65).rstrip('\n')
                ap = AccessPoint(runtime.names['ap'], settings['ssid'], password,
                                 settings['country'], settings.get('dns', '103.86.96.100'),
                                 '/run/phoenix/ap', runtime.run)
                ap.start()
                controller.access_point = ap
            runtime.run(['nft', 'delete', 'table', 'inet', 'phoenix_stop'], optional=True)
            Path('/proc/sys/net/ipv4/ip_forward').write_text('1')
        def tick():
            while not stop.wait(1):
                try:
                    controller.tick()
                except Exception:
                    if runtime:
                        from .stop_guard import block
                        try:
                            block(runtime.run)
                        finally:
                            os._exit(1)
        threading.Thread(target=tick, daemon=True).start()
        if not args.worker_socket:
            print(f'Phoenix administration: http://127.0.0.1:{server.server_port}; token file: {path}', flush=True)
        server.serve_forever()
    finally:
        stop.set()
        if server:
            server.server_close()
        try:
            controller.shutdown()
        finally:
            if runtime:
                Path('/proc/sys/net/ipv4/ip_forward').write_text('0')
            if ap:
                ap.stop()


if __name__ == '__main__':
    main()
