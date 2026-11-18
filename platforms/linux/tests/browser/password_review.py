"""Browser password flow against the disposable Rust ui_harness (HTTPS).

Needs a fresh harness state (`ui_harness.py reset`): initial password
"phoenix". Ends with the login locked out for 5 minutes, so run it last or
reset again afterwards. Disposable passwords only, never device credentials.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = 'https://127.0.0.1:8443'
NEW_PASSWORD = 'Disposable test password 2026'
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    # Disposable self-signed harness certificate only; never the device certificate.
    page = browser.new_page(ignore_https_errors=True, viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE)
    expect(page.locator('#login-credential-label')).to_have_text('Password')
    page.locator('#token').fill('phoenix')
    page.locator('#login-form button').click()
    expect(page.locator('#password-form')).to_be_visible()
    expect(page.locator('#app')).to_be_hidden()
    page.locator('#new-admin-password').fill(NEW_PASSWORD)
    page.locator('#confirm-admin-password').fill(NEW_PASSWORD)
    page.locator('#password-form [type=submit]').click()
    try:
        expect(page.locator('#app')).to_be_visible()
    except Exception:
        print('Password form error:', page.locator('#password-error').inner_text(), 'JS errors:', errors)
        raise
    page.reload()
    expect(page.locator('#app')).to_be_visible()
    page.locator('#logout').click()
    expect(page.locator('#login-form')).to_be_visible()
    page.locator('#token').fill('phoenix')
    page.locator('#login-form button').click()
    expect(page.locator('#login-error')).not_to_be_empty()
    expect(page.locator('#password-form')).to_be_hidden()
    for _ in range(2):
        page.locator('#token').fill('wrong-password')
        page.locator('#login-form button').click()
        expect(page.locator('#login-error')).not_to_be_empty()
    expect(page.locator('#login-form button')).to_be_disabled()
    expect(page.locator('#login-error')).to_contain_text('Accesso sospeso')
    out = Path('results/linux/ui-review/password')
    out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out / 'lockout-desktop.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path=str(out / 'lockout-mobile.png'), full_page=True)
    assert not errors, errors
    browser.close()
    print('Browser password flow: forced change, session reload, logout, old password refused, lockout PASS')
