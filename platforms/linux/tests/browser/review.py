"""Browser regression against the disposable Rust ui_harness (HTTPS, test password only).

Run in the Playwright container with `--network container:<harness>` after
`ui_harness.py start`; PHOENIX_TEST_PASSWORD is the harness test password.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = 'https://127.0.0.1:8443'
engine = os.environ.get('PHOENIX_BROWSER', 'chromium')
assert engine in ('chromium', 'webkit', 'firefox')
password = os.environ['PHOENIX_TEST_PASSWORD']
output = Path('results/linux/ui-review') / engine
output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = getattr(p, engine).launch(headless=True)
    # Disposable self-signed harness certificate only; never the device certificate.
    page = browser.new_page(ignore_https_errors=True, viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    # Records whether #login is ever visible during a page load (also when it is
    # parsed visible, before any script runs).
    page.add_init_script('''window.__loginShown=false;new MutationObserver(()=>{const l=document.getElementById('login');
      if(l&&!l.hidden)window.__loginShown=true;}).observe(document,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden']});''')
    page.goto(BASE)
    expect(page.locator('#login-credential-label')).to_have_text('Password')
    page.locator('#token').fill(password)
    page.locator('#login-form button').click()
    expect(page.locator('#app')).to_be_visible()
    expect(page.locator('#connection-badge')).to_contain_text('Traffico bloccato')
    page.screenshot(path=str(output / 'desktop.png'), full_page=True)
    page.locator('nav a[href="#firewall"]').click()
    page.locator('#add-rule').click()
    page.locator('#rule-form [name="name"]').fill('Browser review <safe>')
    page.locator('#rule-form button[type="submit"]').click()
    expect(page.locator('#save-bar')).to_be_visible()
    page.locator('#save-policy').click()
    expect(page.locator('#save-bar')).to_be_hidden()
    expect(page.locator('#rules-list')).to_contain_text('Browser review <safe>')
    page.reload()
    expect(page.locator('#rules-list')).to_contain_text('Browser review <safe>')
    assert page.evaluate('window.__loginShown') is False, 'login flashed while reloading a signed-in page'
    page.locator('[data-delete="rules"]').click()
    page.locator('#save-policy').click()
    expect(page.locator('#save-bar')).to_be_hidden()
    page.locator('nav a[href="#forwarding"]').click()
    page.locator('#add-forward').click()
    for name, value in {'name': 'Browser forwarding', 'external_port': '8089', 'internal_port': '80', 'target': '192.168.9.20'}.items():
        page.locator('#forward-form [name="' + name + '"]').fill(value)
    page.locator('#forward-form button[type="submit"]').click()
    page.locator('#save-policy').click()
    expect(page.locator('#save-bar')).to_be_hidden()
    expect(page.locator('#forwards-list')).to_contain_text('Browser forwarding')
    page.locator('[data-delete="forwards"]').click()
    page.locator('#save-policy').click()
    expect(page.locator('#save-bar')).to_be_hidden()
    page.route('**/api/v1/status', lambda route: route.abort())
    page.evaluate('poll()')
    expect(page.locator('#offline-banner')).to_be_visible()
    page.unroute('**/api/v1/status')
    page.evaluate('poll()')
    expect(page.locator('#offline-banner')).to_be_hidden()
    for target in ('forwarding', 'nord', 'vpn', 'network', 'system'):
        page.goto(BASE + '/#' + target)
        expect(page.locator('#page-' + target)).to_be_visible()
    # Extended WireGuard import (Linux capability): help text, and a rejected
    # profile reports its specific reason without touching the gateway state.
    page.goto(BASE + '/#vpn')
    expect(page.locator('#wg-help')).to_contain_text('anche con più [Peer]')
    expect(page.locator('#wg-peers-card')).to_be_hidden()
    duplicate_peers = ('[Interface]\nPrivateKey = AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=\nAddress = 10.5.0.2/32\n'
                 '[Peer]\nPublicKey = ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3ODk6Ozw9Pj8=\nEndpoint = 192.0.2.20:51820\nAllowedIPs = 0.0.0.0/0\n'
                 '[Peer]\nPublicKey = ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3ODk6Ozw9Pj8=\nEndpoint = 192.0.2.21:51820\nAllowedIPs = 0.0.0.0/0\n')
    page.locator('#wg-profile').fill(duplicate_peers)
    page.locator('#wg-form [type=submit]').click()
    page.locator('#confirm-ok').click()
    expect(page.locator('#notice')).to_contain_text('stessa chiave pubblica')
    expect(page.locator('#wg-profile')).not_to_have_value('')
    page.locator('#wg-profile').fill('')
    # Peer list (multi-peer profiles): status augmented in the browser only.
    peers = [
        {'group': 0, 'public_key_fingerprint': 'AQEBAQEB…', 'endpoint': '192.0.2.20:51999', 'address': None,
         'allowed_ips': ['0.0.0.0/0'], 'active': False, 'latest_handshake_age_s': None, 'connected': False},
        {'group': 1, 'public_key_fingerprint': 'AgICAgIC…', 'endpoint': '<b>site</b>.example:51821', 'address': '192.0.2.21',
         'allowed_ips': ['10.88.0.0/24'], 'active': True, 'latest_handshake_age_s': None, 'connected': False},
        {'group': 0, 'public_key_fingerprint': 'AwMDAwMD…', 'endpoint': '192.0.2.20:51820', 'address': '192.0.2.20',
         'allowed_ips': ['0.0.0.0/0'], 'active': True, 'latest_handshake_age_s': 4, 'connected': True},
    ]
    def with_peers(route):
        response = route.fetch()
        body = response.json()
        body.update(provider='wireguard', peers=peers)
        route.fulfill(response=response, json=body)
    page.route('**/api/v1/vpn', with_peers)
    page.evaluate('poll()')
    card = page.locator('#wg-peers-card')
    expect(card).to_be_visible()
    expect(page.locator('#wg-peers .rule-item')).to_have_count(3)
    for text in ('Riserva', 'Senza handshake', 'Attivo', 'handshake 0m 4s fa', '<b>site</b>.example:51821 · 192.0.2.21'):
        expect(card).to_contain_text(text)
    assert page.locator('#wg-peers b').count() == 0, 'peer fields must be rendered as text'
    page.unroute('**/api/v1/vpn')
    page.evaluate('poll()')
    expect(card).to_be_hidden()
    page.goto(BASE + '/#network')
    expect(page.locator('#save-uplink')).to_be_disabled()
    page.locator('[data-action="direct"]').click()
    page.locator('#confirm-cancel').click()
    expect(page.locator('#connection-badge')).to_contain_text('Traffico bloccato')
    for width in (390, 320):
        page.set_viewport_size({'width': width, 'height': 844})
        for target in ('overview', 'firewall', 'forwarding', 'nord', 'vpn', 'network', 'system'):
            page.goto(BASE + '/#' + target)
            expect(page.locator('#page-' + target)).to_be_visible()
            sizes = page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
            assert sizes['scroll'] <= sizes['width'] + 1, (width, target, sizes)
        page.goto(BASE + '/#nord')
        page.screenshot(path=str(output / f'mobile-{width}.png'), full_page=True)
    page.goto(BASE + '/#system')
    page.evaluate("document.getElementById('wifi-password').value='fictitious-only'")
    page.locator('#logout-system').click()
    expect(page.locator('#wifi-password')).to_have_value('')
    expect(page.locator('#login')).to_be_visible()
    # One failure per engine; the next successful login resets the counter,
    # so three engines never reach the 3-failure lockout.
    page.locator('#token').fill('wrong-test-password')
    page.locator('#login-form button').click()
    expect(page.locator('#login-error')).not_to_be_empty()
    expect(page.locator('#app')).to_be_hidden()
    assert not errors, errors
    print(json.dumps({'browser': engine, 'pages': 7, 'widths': [1440, 390, 320], 'policy_roundtrip': True,
                      'forwarding_roundtrip': True, 'reload_without_login_flash': True, 'wireguard_import_rejection': True, 'peer_list': True, 'offline_recovery': True, 'logout_invalid_login': True,
                      'javascript_errors': errors}))
    browser.close()
