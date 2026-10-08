from pathlib import Path
import json
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'data.live.js').read_text(encoding='utf-8')
data = json.loads(raw.split('=', 1)[1].strip().removesuffix(';'))
rows = data['rows']
ranked = [row for row in rows if row.get('rankingEligible') is not False]
assert rows and len({r['id'] for r in rows}) == len(rows)
for row in rows:
    for link in row.get('outboundLinks',[]):
        assert set(link)=={'source','label','id'}
        assert link['id'].startswith('o-') and 'http' not in json.dumps(link)
    assert set(row['costs']) == {'3','promo'}
    if row.get('rankingEligible') is False:
        assert all(value is None for value in row['costs'].values())
    else:
        assert isinstance(row['costs']['3'], (int,float))
        if row['months'] is None:
            assert row['costs']['promo'] is None
        else:
            assert isinstance(row['costs']['promo'], (int,float))

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width':390,'height':844})
    page.set_default_timeout(10000)
    errors=[]
    page.on('pageerror', lambda error: errors.append(str(error)))
    # The layout must survive a failed separate stylesheet request.
    page.route('**/styles.css', lambda route: route.abort())
    root = ROOT.as_uri()
    page.goto(root+'/index.html')
    assert page.locator('style[data-preview-style]').count()==1
    assert page.locator('.hero').evaluate('(el)=>getComputedStyle(el).borderRadius')=='22px'
    assert page.locator('.result-link').count()==len(rows)
    assert page.locator('[data-months]').count()==0
    for profile in ('7plus','15plus','11daily','100plus','daily','capped','other_unlimited'):
        page.select_option('#profile',profile)
        assert page.locator('.result-link').count()==sum(r['category']==profile for r in rows)
    page.select_option('#profile','all')
    ids=page.locator('#results .result-link').evaluate_all('(links)=>links.map(a=>new URL(a.href).searchParams.get("id"))')
    costs={r['id']:r['costs']['3'] for r in ranked}
    assert [costs[i] for i in ids]==sorted(costs.values())
    page.select_option('#profile','7plus')
    page.locator('.extras summary').click()
    page.select_option('#brand','티플러스')
    count=page.locator('.result-link').count()
    with page.expect_navigation(wait_until='load'):
        page.locator('#results .result-link').first.click()
    page.screenshot(path='preview-detail.png')
    assert not errors,errors
    expect(page.locator('.metric')).to_have_count(2)
    assert page.locator('.metric.primary').inner_text().startswith('3개월')
    assert page.locator('.post').evaluate('(el)=>getComputedStyle(el).borderRadius')=='22px'
    with page.expect_navigation(wait_until='load'):
        page.locator('#backLink').click()
    assert page.locator('#profile').input_value()=='7plus'
    assert page.locator('#brand').input_value()=='티플러스'
    assert page.locator('.result-link').count()==count
    assert page.locator('.extras').evaluate('(el)=>el.open')
    page.goto(root+'/index.html')
    for row in (r for r in rows if r['moyoCrosscheck'].get('specDiffs')):
        page.goto(root+'/detail.html?id='+row['id'])
        assert '사양 검토 필요' in page.locator('#verification').inner_text()
    review=next((r for r in rows if r.get('rankingEligible') is False),None)
    if review:
        page.goto(root+'/detail.html?id='+review['id'])
        assert '공식 검증 대기' in page.locator('#costMetrics').inner_text()
    promo=next(r for r in ranked if r['months'] is not None)
    page.goto(root+'/detail.html?id='+promo['id'])
    assert f"{promo['months']}개월 할인 총요금" in page.locator('#costMetrics').inner_text()
    assert page.locator('#sourceLinks a').count()==0
    assert page.locator('#sourceLinks button:disabled').count()>0
    page.screenshot(path='preview-detail.png')
    page.add_init_script("window.OUTBOUND_SERVICE_ORIGIN='https://outbound.example.test'")
    page.goto(root+'/detail.html?id='+promo['id'])
    hrefs=page.locator('#sourceLinks a').evaluate_all('(links)=>links.map(a=>a.href)')
    assert hrefs and all(href.startswith('https://outbound.example.test/out/o-') for href in hrefs)
    assert page.locator('#sourceLinks button:disabled').count()==0
    page.goto(root+'/detail.html?id=missing')
    assert '요금제를 찾을 수 없습니다' in page.locator('#post').inner_text()
    page.goto(root+'/index.html')
    for width in (320,390,768,1440):
        page.set_viewport_size({'width':width,'height':900})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        if width in (390,1440):page.screenshot(path=f'preview-{width}.png')
    assert not errors,errors
    browser.close()
print(json.dumps({'rows':len(rows),'ranked':len(ranked),'status':'passed'},ensure_ascii=False))
