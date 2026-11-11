"""Serialized control plane; accepted configuration is not proof of connectivity."""
from copy import deepcopy
import threading
import time
from .store import ConfigStore, RevisionConflict
from .vault import Vault
from .history import History
from .policy import validate, boolean, integer
from .wireguard import parse
from .rotation import Rotation, choose_country
from . import nord
from . import station as station_module


class Unavailable(Exception):
    pass


class Controller:
    def __init__(self, directory, countries, runtime=None):
        self.lock = threading.RLock()
        self.dispatch_lock = threading.Lock()
        self.busy = False
        self.closing = False
        self.updating = False
        self.store = ConfigStore(directory)
        self.vault = Vault(directory)
        self.history = History(self.store)
        self.countries = countries
        self.runtime = runtime
        self.access_point = None
        self.station = None
        self.updates = None
        self.ap_suspended = False
        self.base_ap = runtime.names["ap"] if runtime else None
        self.settings = self.vault.load()
        self.timer = Rotation(time.monotonic)
        self.error = ''
        self.exit_ip = ''
        self.exit_country = ''
        self.api_verified = False
        self.connected_recorded = False
        self.location = {}
        self.enabled = False
        self.want_connected = False
        self.retry_at = None
        self.retry_count = 0
        self.connect_started = 0
        self.started = time.monotonic()
        # Reboot always starts blocked; explicit connect restores the saved profile.
        if runtime:
            runtime.block(self.policy())

    def validate_command(self, body):
        if not isinstance(body, dict):
            raise ValueError('object_required')
        action = body.get('action')
        if action not in ('wireguard', 'nordvpn', 'connect', 'rotate', 'verify_exit',
                          'catalog_test', 'disconnect', 'direct', 'forget', 'wifi', 'uplink'):
            raise ValueError('unsupported_action')
        if action == 'wifi':
            if not self.station:
                raise Unavailable('wifi_not_configured')
            station_module.validate(body)
        elif action == 'uplink':
            if body.get('uplink') not in ('wifi', 'ethernet'):
                raise ValueError('invalid_uplink')
            if body['uplink'] == 'wifi' and (not self.station or not self.station.current):
                raise ValueError('wifi_profile_required')
        elif action == 'wireguard':
            parse(body.get('profile', ''))
        elif action == 'nordvpn':
            boolean(body.get('rotation'))
            integer(body.get('interval'), 30, 86400)
            exclude = boolean(body.get('exclude_restricted', False))
            choose_country([c['code'] for c in self.countries], body.get('country', ''), exclude=exclude)
            token = body.get('token', '')
            if not isinstance(token, str) or len(token) > 512 or any(ord(c) < 33 for c in token):
                raise ValueError('invalid_token')
            if not token:
                nord.key(self.settings.get('nord_key', ''))
        elif action in ('connect', 'rotate'):
            if self.settings.get('provider') not in ('wireguard', 'nordvpn'):
                raise ValueError('profile_required')
            if action == 'rotate' and self.settings['provider'] != 'nordvpn':
                raise ValueError('nordvpn_required')

    def submit(self, body):
        self.require_runtime()
        if not self.lock.acquire(blocking=False):
            raise RevisionConflict('command_in_progress')
        try:
            if self.busy or self.closing or self.updating:
                raise RevisionConflict('command_in_progress')
            self.validate_command(body)
            body = deepcopy(body)
            self.busy = True
            def work():
                with self.lock:
                    try:
                        self.command(body)
                    except Exception:
                        if body['action'] in ('verify_exit', 'catalog_test'):
                            self.error = 'exit_check_failed' if body['action'] == 'verify_exit' else 'nord_api_unavailable'
                            if body['action'] == 'verify_exit':
                                self.exit_ip = self.exit_country = ''
                            else:
                                self.api_verified = False
                        else:
                            self.error = 'vpn_operation_failed'
                            if body['action'] in ('wifi', 'uplink'):
                                self.want_connected = False
                                self.retry_at = None
                                self.error = 'network_setup_failed'
                            self.schedule_retry()
                            self.enabled = False
                            self.timer.disconnected()
                            try:
                                self.runtime.block(self.policy())
                            except Exception:
                                self.runtime.enforced = False
                                self.error = 'firewall_enforcement_failed'
                    finally:
                        self.busy = False
            threading.Thread(target=work, daemon=True).start()
        finally:
            self.lock.release()
        return {'accepted': True}

    def shutdown(self):
        with self.lock:
            self.closing = True
            self.want_connected = self.enabled = False
            self.retry_at = None
            self.timer.disconnected()
            if self.runtime:
                self.runtime.disconnect(self.policy())
                if self.runtime.selected_route:
                    for priority in ('17690', '17710', '17711'):
                        self.runtime.run(['ip', 'rule', 'del', 'priority', priority], optional=True)
            if self.station:
                self.station.disconnect()
                if self.access_point and self.ap_suspended and self.station.name == self.base_ap:
                    self.runtime.run(['nmcli', 'device', 'set', self.station.name, 'managed', 'no'])

    def require_runtime(self):
        if self.runtime is None:
            raise Unavailable('target_network_not_initialized')

    def policy(self):
        saved = self.store.load()
        policy = saved['desired'].get('policy', {'default_allow': True, 'rules': [], 'forwards': []}).copy()
        policy['revision'] = saved['revision']
        for forward in policy['forwards']:
            forward['active'] = bool(self.runtime and self.runtime.enforced and self.runtime.mode == ('vpn' if forward['vpn'] else 'direct') and forward['enabled'])
        return policy

    def save_policy(self, body):
        with self.lock:
            self.require_runtime()
            if self.busy or self.closing or self.updating:
                raise RevisionConflict('command_in_progress')
            policy = validate(body)
            current = self.store.load()
            if policy['revision'] != current['revision']:
                raise RevisionConflict('revision_conflict_reload')
            mode = self.runtime.mode
            self.runtime.block(self.policy())
            desired = dict(current['desired'], policy=policy)
            # Save only after the drop barrier. Apply failure leaves traffic blocked.
            self.store.save(current['revision'], desired, lambda d: validate(d['policy']))
            try:
                self.runtime.firewall(policy, mode)
            except Exception:
                self.runtime.block(policy)
                raise
            return self.policy()

    def schedule_retry(self):
        if self.want_connected:
            self.retry_count += 1
            self.retry_at = time.monotonic() + min(60, 5 * 2 ** min(self.retry_count - 1, 4))

    def _connect(self):
        self.require_runtime()
        if self.settings.get('provider') not in ('wireguard', 'nordvpn'):
            raise ValueError('profile_required')
        self.want_connected = True
        self.retry_at = None
        self.connect_started = time.monotonic()
        self.runtime.block(self.policy())
        self.exit_ip = self.exit_country = ''
        self.enabled = False
        self.timer.disconnected()
        self.connected_recorded = False
        if self.settings.get('provider') == 'nordvpn':
            profile, location = nord.select(self.settings['nord_key'], self.countries,
                fixed=self.settings.get('country', ''), previous=self.location.get('country', ''),
                exclude=self.settings.get('exclude_restricted', False), previous_server=self.location.get('id', 0), request=self.runtime.nord_request)
            self.location = location
        else:
            profile = parse(self.settings.get('profile', ''))
            self.location = {'country': '', 'server': profile.endpoint, 'id': 0}
        if self.access_point:
            self.access_point.set_dns(profile.dns)
        self.runtime.connect(self.policy(), profile)
        self.enabled = True
        self.error = ''

    def network_command(self, body):
        desired = 'wifi' if body['action'] == 'wifi' else body['uplink']
        resume_vpn = self.want_connected
        resume_direct = self.runtime.mode == 'direct'
        self.runtime.disconnect(self.policy())
        self.enabled = False
        self.timer.disconnected()
        self.retry_at = None
        if desired == 'wifi':
            if self.station.name == self.base_ap:
                if self.access_point and self.access_point.active:
                    self.access_point.stop()
                self.ap_suspended = True
            gateway = self.station.connect(body) if body['action'] == 'wifi' else self.station.reconnect()
            self.runtime.select_uplink(self.policy(), self.station.name, 'wifi', gateway,
                                       ap_name='phapoff' if self.ap_suspended else self.base_ap)
        else:
            if self.station:
                self.station.disconnect()
            self.runtime.select_uplink(self.policy(), self.runtime.ethernet_name, 'ethernet', ap_name=self.base_ap)
            if self.ap_suspended and self.access_point:
                self.runtime.run(['nmcli', 'device', 'set', self.station.name, 'managed', 'no'])
                self.access_point.start()
            self.ap_suspended = False
        if resume_vpn:
            self._connect()
        elif resume_direct:
            self.runtime.direct(self.policy())

    def command(self, body):
        with self.lock:
            self.require_runtime()
            action = body.get('action')
            if action in ('wifi', 'uplink'):
                self.network_command(body)
            elif action == 'wireguard':
                parse(body['profile'])
                self.settings = dict(provider='wireguard', profile=body['profile'], rotation=False)
                self.vault.save(self.settings)
                self._connect()
            elif action == 'nordvpn':
                fixed = body.get('country', '')
                rotation = boolean(body['rotation'])
                interval = integer(body['interval'], 30, 86400)
                exclude = boolean(body.get('exclude_restricted', False))
                choose_country([c['code'] for c in self.countries], fixed=fixed, exclude=exclude)
                private = nord.provision(body['token'], request=self.runtime.nord_request) if body.get('token') else self.settings.get('nord_key', '')
                nord.key(private)
                self.settings = dict(provider='nordvpn', nord_key=private, country=fixed,
                                     rotation=rotation, interval=interval, exclude_restricted=exclude)
                self.vault.save(self.settings)
                self._connect()
            elif action in ('connect', 'rotate'):
                if action == 'rotate' and self.settings.get('provider') != 'nordvpn':
                    raise ValueError('nordvpn_required')
                self._connect()
            elif action == 'verify_exit':
                self.exit_ip, self.exit_country = self.runtime.verify_exit()
            elif action == 'catalog_test':
                result = self.runtime.nord_request('/v1/servers/countries')
                if not isinstance(result, list) or not result:
                    raise ValueError('nord_api_unavailable')
                self.api_verified = True
            elif action in ('disconnect', 'direct', 'forget'):
                self.want_connected = False
                self.retry_at = None
                self.runtime.block(self.policy())
                self.enabled = False
                self.exit_ip = self.exit_country = ''
                self.timer.disconnected()
                if action == 'direct':
                    if self.access_point:
                        self.access_point.set_dns(self.access_point.default_dns)
                    self.runtime.direct(self.policy())
                else:
                    self.runtime.disconnect(self.policy())
                if action == 'forget':
                    self.settings = {}
                    self.vault.save({})
            else:
                raise Unavailable('action_not_implemented')
            self.error = ''
            return self.vpn_status()

    def tick(self):
        with self.lock:
            if self.runtime is None or self.busy or self.closing or self.updating:
                return
            try:
                if self.access_point and not self.ap_suspended and not self.access_point.healthy():
                    self.want_connected = self.enabled = False
                    self.retry_at = None
                    self.error = 'ap_service_failed'
                    self.runtime.block(self.policy())
                    return
                if self.retry_at is not None and time.monotonic() >= self.retry_at:
                    self._connect()
                if not self.enabled:
                    return
                connected = self.runtime.handshake()
                if connected:
                    self.retry_count = 0
                if connected and not self.connected_recorded:
                    self.history.add_confirmed(self.location.get('country', ''), self.location.get('server', ''), self.location.get('id', 0))
                    self.connected_recorded = True
                    self.timer.connected(self.settings.get('rotation', False), self.settings.get('interval', 300))
                if not connected:
                    had_session = self.connected_recorded
                    self.timer.disconnected()
                    self.connected_recorded = False
                    if had_session or time.monotonic() - self.connect_started > 30:
                        self.runtime.block(self.policy())
                        self.enabled = False
                        self.schedule_retry()
                if self.timer.due():
                    self._connect()
            except Exception:
                self.error = 'vpn_operation_failed'
                self.schedule_retry()
                self.enabled = False
                self.timer.disconnected()
                self.runtime.block(self.policy())

    def vpn_status(self):
        connected = bool(not self.busy and self.runtime and self.enabled and self.runtime.handshake())
        direct = bool(self.runtime and self.runtime.mode == 'direct')
        return {'provider': self.settings.get('provider', ''), 'enabled': self.enabled,
                'state': 'provisioning' if self.busy else 'error' if self.error else 'direct' if direct else 'connected' if connected else 'connecting' if self.enabled else 'blocked',
                'busy': self.busy, 'error': self.error, 'country': self.settings.get('country', ''),
                'server': self.location.get('server', ''), 'server_country': self.location.get('country', ''),
                'account_configured': bool(self.settings.get('nord_key')),
                'rotation': self.settings.get('rotation', False), 'interval': self.settings.get('interval', 300),
                'exclude_restricted': self.settings.get('exclude_restricted', False),
                'next_rotation_seconds': self.timer.remaining(), 'exit_ip': self.exit_ip, 'exit_country': self.exit_country,
                'api_verified': self.api_verified, 'endpoint': self.runtime.profile.endpoint if self.runtime and self.runtime.profile else ''}
