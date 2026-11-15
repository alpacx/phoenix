"""HTTPS password endpoints. Cookies never exposed to browser JavaScript."""
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
from .jsonutil import loads

COOKIE = '__Host-phoenix'


def session(request):
    try:
        if len(request.headers.get_all('Cookie', [])) > 1:
            return ''
        cookies = SimpleCookie(request.headers.get('Cookie', ''))
        return cookies[COOKIE].value if COOKIE in cookies else ''
    except Exception:
        return ''


def route(request, api):
    path = urlsplit(request.path).path
    if not path.startswith('/api/v1/auth/') or not getattr(request.server, 'password_auth', False):
        return False
    if not request.valid_origin(require_origin=request.command == 'POST'):
        return True
    action = path.rsplit('/', 1)[-1]
    if (request.command, action) not in {('GET', 'status'), ('POST', 'login'), ('POST', 'logout'), ('POST', 'password')}:
        request.send(405, {'error': 'method_not_allowed'})
        return True
    try:
        args = {}
        if request.command == 'POST':
            lengths = request.headers.get_all('Content-Length', [])
            if (request.headers.get('Transfer-Encoding') or len(lengths) != 1
                    or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= 4096
                    or request.headers.get_content_type() != 'application/json'):
                request.send(400, {'error': 'invalid_request'})
                return True
            args = loads(request.rfile.read(int(lengths[0])))
            if not isinstance(args, dict):
                raise ValueError('object_required')
        args['session'] = session(request)
        value = api.call('auth_' + action, args)
        new_session = value.pop('session', None)
        headers = {}
        if new_session is not None or action == 'logout':
            headers['Set-Cookie'] = (COOKIE + '=' + (new_session or '')
                + '; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age='
                + ('0' if action == 'logout' else ('600' if value.get('must_change') else '3600')))
        code = 200
        if value.get('ok') is False:
            code = 429 if value.get('error') == 'login_locked' else 401
            if code == 429:
                headers['Retry-After'] = str(value['retry_after'])
        request.send(code, value, extra_headers=headers)
    except Exception:
        request.send(503, {'error': 'authentication_unavailable'})
    return True
