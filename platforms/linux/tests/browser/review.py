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
                      'forwarding_roundtrip': True, 'reload_without_login_flash': True, 'offline_recovery': True, 'logout_invalid_login': True,
                      'javascript_errors': errors}))
    browser.close()
