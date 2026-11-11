"""Browser regression against the disposable ui_harness (test token only)."""
import json
import os
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

engine=os.environ.get('PHOENIX_BROWSER','chromium')
assert engine in ('chromium','webkit','firefox')
output=Path('results/linux/ui-review')/engine;output.mkdir(parents=True,exist_ok=True)
headers={'Authorization':'Bearer '+'a'*64,'Content-Type':'application/json'}
request=urllib.request.Request('http://127.0.0.1:18086/api/v1/policy',headers=headers)
deadline=time.monotonic()+15
while True:
    try:
        with urllib.request.urlopen(request,timeout=2) as response:
            policy=json.load(response)
        break
    except OSError:
        if time.monotonic()>=deadline:
            raise
        time.sleep(.2)
policy.update(rules=[],forwards=[])
with urllib.request.urlopen(urllib.request.Request(request.full_url,data=json.dumps(policy).encode(),headers=headers)) as response:
    assert response.status==200
with sync_playwright() as p:
    browser=getattr(p,engine).launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:18086')
    page.locator('#token').fill('a'*64)
    page.locator('#login-form button').click()
    expect(page.locator('#app')).to_be_visible()
    expect(page.locator('#connection-badge')).to_contain_text('Traffico bloccato')
    page.screenshot(path=str(output/'desktop.png'),full_page=True)
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
    page.locator('[data-delete="rules"]').click()
    page.locator('#save-policy').click()
    expect(page.locator('#save-bar')).to_be_hidden()
    page.locator('nav a[href="#forwarding"]').click()
    page.locator('#add-forward').click()
    for name,value in {'name':'Browser forwarding','external_port':'8089','internal_port':'80','target':'192.168.9.20'}.items():
        page.locator('#forward-form [name="'+name+'"]').fill(value)
    page.locator('#forward-form button[type="submit"]').click()
    page.locator('#save-policy').click()
    expect(page.locator('#save-bar')).to_be_hidden()
    expect(page.locator('#forwards-list')).to_contain_text('Browser forwarding')
    page.locator('[data-delete="forwards"]').click()
    page.locator('#save-policy').click()
    expect(page.locator('#save-bar')).to_be_hidden()
    page.route('**/api/v1/status',lambda route:route.abort())
    page.evaluate('poll()')
    expect(page.locator('#offline-banner')).to_be_visible()
    page.unroute('**/api/v1/status')
    page.evaluate('poll()')
    expect(page.locator('#offline-banner')).to_be_hidden()
    for target in ('forwarding','nord','vpn','network','system'):
        page.goto('http://127.0.0.1:18086/#'+target)
        expect(page.locator('#page-'+target)).to_be_visible()
    page.goto('http://127.0.0.1:18086/#network')
    expect(page.locator('#save-uplink')).to_be_disabled()
    page.locator('[data-action="direct"]').click()
    page.locator('#confirm-cancel').click()
    expect(page.locator('#connection-badge')).to_contain_text('Traffico bloccato')
    for width in (390,320):
        page.set_viewport_size({'width':width,'height':844})
        for target in ('overview','firewall','forwarding','nord','vpn','network','system'):
            page.goto('http://127.0.0.1:18086/#'+target)
            expect(page.locator('#page-'+target)).to_be_visible()
            sizes=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
            assert sizes['scroll']<=sizes['width']+1,(width,target,sizes)
        page.goto('http://127.0.0.1:18086/#nord')
        page.screenshot(path=str(output/f'mobile-{width}.png'),full_page=True)
    page.goto('http://127.0.0.1:18086/#system')
    page.evaluate("document.getElementById('wifi-password').value='fictitious-only'")
    page.locator('#logout-system').click()
    expect(page.locator('#wifi-password')).to_have_value('')
    expect(page.locator('#login')).to_be_visible()
    page.locator('#token').fill('b'*64)
    page.locator('#login-form button').click()
    expect(page.locator('#login-error')).not_to_be_empty()
    assert not errors,errors
    print(json.dumps({'browser':engine,'pages':7,'widths':[1440,390,320],'policy_roundtrip':True,'forwarding_roundtrip':True,'offline_recovery':True,'logout_invalid_login':True,'javascript_errors':errors}))
    browser.close()
