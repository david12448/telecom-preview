from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'data.live.js').read_text(encoding='utf-8')
data = json.loads(raw.split('=', 1)[1].strip().removesuffix(';'))
rows = data['rows']
assert rows and len({r['id'] for r in rows}) == len(rows)
for row in rows:
    assert row['id'].startswith('p-')
    for n in (3, 6, 12):
        months = row['months']
        base = n * row['promo'] if months is None else min(n, months) * row['promo'] + max(0, n-months) * row['after']
        assert row['costs'][str(n)] >= base, (row['id'], n)
    if row['category'] in ('7plus', '15plus'):
        assert row['data'] == (7 if row['category'] == '7plus' else 15) and row['qos'] > 0

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    root = ROOT.as_uri()
    page.goto(root + '/index.html')
    assert page.locator('.result-link').count() == len(rows)
    for profile in ('7plus','15plus','11daily','100plus','daily','capped','other_unlimited'):
        page.select_option('#profile', profile)
        assert page.locator('.result-link').count() == sum(r['category'] == profile for r in rows)
    for n in (3, 6, 12):
        page.select_option('#profile', 'all')
        page.locator(f'[data-months="{n}"]').click()
        ids = page.locator('.result-link').evaluate_all('(links)=>links.map(a=>new URL(a.href).searchParams.get("id"))')
        costs = {r['id']: r['costs'][str(n)] for r in rows}
        assert [costs[i] for i in ids] == sorted(costs.values())
    page.select_option('#profile', '7plus')
    page.select_option('#brand', '티플러스')
    count = page.locator('.result-link').count()
    page.locator('.result-link').first.click()
    assert 'months=12' in page.url
    assert page.locator('.metric.primary').inner_text().startswith('12개월')
    page.locator('#backLink').click()
    assert page.locator('#profile').input_value() == '7plus'
    assert page.locator('#brand').input_value() == '티플러스'
    assert page.locator('.result-link').count() == count
    for row in (r for r in rows if r['moyoCrosscheck'].get('specDiffs')):
        page.goto(root + '/detail.html?id=' + row['id'])
        assert '사양 검토 필요' in page.locator('#verification').inner_text()
        assert page.locator('#sourceLinks .disabled').count() == 0
    page.goto(root + '/detail.html?id=missing')
    assert '요금제를 찾을 수 없습니다' in page.locator('#post').inner_text()
    page.goto(root + '/index.html')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path='preview-mobile.png')
    page.set_viewport_size({'width': 1440, 'height': 900})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path='preview-desktop.png')
    assert not errors, errors
    browser.close()
print(json.dumps({'rows':len(rows), 'carriers':data['carrierScope'], 'status':'passed'}, ensure_ascii=False))
