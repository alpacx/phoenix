"""Disposable HTTPS password flow; fake dataplane, no device credentials."""
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
from playwright.sync_api import sync_playwright, expect
from phoenix_linux.controller import Controller
from phoenix_linux.frontend import TLSHTTPServer
from phoenix_linux.server import handler
from phoenix_linux.runtime import Runtime
from test_runtime import FakeRunner
from test_policy import NAMES

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                    '-keyout', str(root/'key.pem'), '-out', str(root/'cert.pem'),
                    '-days', '1', '-subj', '/CN=localhost'], check=True, capture_output=True)
    controller = Controller(root/'state', [], Runtime(NAMES, FakeRunner()))
    controller.runtime.status = lambda: dict(uplink='ethernet', uplink_ready=False, ethernet_link=False, ethernet_ip=False, wifi_link=False, wifi_ip=False, ap_active=False, usb_configured=True, usb_mounted=True, usb_suspended=False, vpn_up=False, direct=False, allowed=0, blocked=0, malformed=0, heap_free=1000000, uptime_ms=1000, firewall_enforced=True, counter_scope='fixture', malformed_counter_available=False)
    server = TLSHTTPServer(('127.0.0.1', 0), handler(controller, 'a'*64))
    server.tls = server.password_auth = True
    server.allow_bearer = False
    server.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.context.load_cert_chain(root/'cert.pem', root/'key.pem')
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Disposable fixture only: never used for the real device certificate.
            page = browser.new_page(ignore_https_errors=True, viewport={'width':1440,'height':1000})
            errors=[]
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'https://127.0.0.1:{server.server_port}')
            expect(page.locator('#login-credential-label')).to_have_text('Password')
            page.locator('#token').fill('phoenix')
            page.locator('#login-form button').click()
            expect(page.locator('#password-form')).to_be_visible()
            expect(page.locator('#app')).to_be_hidden()
            page.locator('#new-admin-password').fill('Disposable test password 2026')
            page.locator('#confirm-admin-password').fill('Disposable test password 2026')
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
            for i in range(3):
                page.locator('#token').fill('wrong-password')
                page.locator('#login-form button').click()
                expect(page.locator('#login-error')).not_to_be_empty()
            expect(page.locator('#login-form button')).to_be_disabled()
            out=Path('results/linux/ui-review/password');out.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(out/'lockout-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            page.screenshot(path=str(out/'lockout-mobile.png'),full_page=True)
            assert not errors, errors
            browser.close()
            print('Browser password flow: forced change, session reload, logout, lockout PASS')
    finally:
        server.shutdown();server.server_close();thread.join()
