import json, sys, re, time, socket, ssl, urllib.request
from urllib.parse import urlparse, parse_qs
probe_p, out_p, use_browser, maxsites = sys.argv[1], sys.argv[2], sys.argv[3] == '1', int(sys.argv[4])
probe = json.load(open(probe_p, encoding='utf-8'))
UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36'
def pick_urls():
    chosen = {}
    for u in probe['urls']:
        h = urlparse(u).netloc.lower()
        if h in probe['sites'] and h not in chosen: chosen[h] = u
    return list(chosen.items())[:maxsites]
def static_check(url):
    r = {'url': url}; t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9'})
        with urllib.request.urlopen(req, timeout=25, context=ssl.create_default_context()) as resp:
            first = resp.read(1); r['ttfb_ms'] = round((time.time() - t0) * 1000); body = first + resp.read(2_000_000)
            r['status'] = resp.status; r['final_url'] = resp.geturl(); r['bytes'] = len(body)
            r['server'] = resp.headers.get('server'); r['powered_by'] = resp.headers.get('x-powered-by')
        h = body.decode('utf-8', 'ignore')
        r['markers'] = {k: bool(re.search(p, h, re.I)) for k, p in {
            'fbevents_js': r'connect\.facebook\.net/[^"\']*fbevents\.js', 'fbq_call': r'\bfbq\s*\(', 'noscript_pixel': r'facebook\.com/tr\?id=',
            'gtm': r'googletagmanager\.com/gtm\.js', 'gtag': r'gtag\(', 'shopify': r'cdn\.shopify\.com|Shopify\.theme', 'woocommerce': r'woocommerce|wp-content',
            'bigcommerce': r'bigcommerce\.com|cdn11\.bigcommerce', 'webflow': r'webflow', 'klaviyo': r'klaviyo', 'tiktok_pixel': r'analytics\.tiktok\.com'}.items()}
        r['pixel_ids_in_html'] = sorted(set(re.findall(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"](\d{8,})", h) + re.findall(r'facebook\.com/tr\?id=(\d{8,})', h)))
        r['gtm_ids'] = sorted(set(re.findall(r'GTM-[A-Z0-9]{4,8}', h)))
        r['note'] = 'static HTML only: pixels injected by GTM/JS will NOT show here; see browser result'
    except Exception as e: r['error'] = repr(e)[:200]
    return r
def browser_check(url):
    from playwright.sync_api import sync_playwright
    reqs = []; r = {'url': url}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, user_agent=UA, is_mobile=True, has_touch=True)
        pg = ctx.new_page(); pg.on('request', lambda q: reqs.append(q.url))
        try:
            pg.goto(url, wait_until='load', timeout=35000); pg.wait_for_timeout(7000)
            r['perf'] = pg.evaluate("()=>{const n=performance.getEntriesByType('navigation')[0]||{};return {ttfb_ms:n.responseStart,load_ms:n.loadEventEnd}}")
            r['lcp_ms'] = pg.evaluate("()=>new Promise(res=>{let v=null;try{new PerformanceObserver(l=>{const e=l.getEntries();v=e[e.length-1].startTime}).observe({type:'largest-contentful-paint',buffered:true})}catch(e){}setTimeout(()=>res(v),600)})")
            r['small_tap_targets'] = pg.evaluate("()=>{const els=[...document.querySelectorAll('a,button,input,select,[role=button]')].filter(e=>{const b=e.getBoundingClientRect();return b.width>0&&b.height>0});return {total:els.length,under_44px:els.filter(e=>{const b=e.getBoundingClientRect();return b.width<44||b.height<44}).length}}")
            r['title'] = pg.title()
        except Exception as e: r['error'] = repr(e)[:200]
        b.close()
    px = [u for u in reqs if re.search(r'facebook\.com/tr[/?]|facebook\.net/.*/fbevents', u)]
    ev = []; pii = []
    for u in px:
        q = parse_qs(urlparse(u).query)
        if 'ev' in q: ev.append({'id': q.get('id', [''])[0], 'event': q['ev'][0]})
        for k, v in q.items():
            if k.startswith('ud[') or k.startswith('ud%5B'):
                if not re.fullmatch(r'[0-9a-f]{64}', v[0] or ''): pii.append({'param': k, 'looks_hashed': False})
    r.update({'total_requests': len(reqs), 'meta_pixel_requests': len(px), 'meta_events_seen': ev, 'unhashed_user_data_params': pii,
              'capi_note': 'server-side CAPI is invisible from outside; absence here proves nothing about CAPI'})
    return r
def judge(text, s, br):
    t = text.lower(); v = []
    pix_seen = (br or {}).get('meta_pixel_requests'); st = (s or {}).get('markers', {})
    if 'pixel' in t and re.search(r'not (firing|fire|detected|found|installed|present)|no (meta )?pixel|missing|fail', t) and 'purchase' not in t:
        if br and 'error' not in br: v.append(('pixel absent/not firing', 'CONTRADICTED' if pix_seen else 'SUPPORTED', f'browser saw {pix_seen} pixel requests'))
        elif st: v.append(('pixel absent/not firing', 'WEAK-CONTRADICTED(static)' if (st.get('fbevents_js') or st.get('fbq_call')) else 'UNCONFIRMED(static misses GTM)', str(st)))
    if re.search(r'purchase', t) and re.search(r'missing|not|no ', t):
        v.append(('purchase event missing', 'UNTESTABLE-WITHOUT-CHECKOUT', 'landing-page visit cannot fire Purchase; check how engine decided this'))
    if re.search(r'unhash|pii|plain.?text|email', t):
        if br: v.append(('unhashed PII', 'CONTRADICTED' if not br.get('unhashed_user_data_params') else 'SUPPORTED', str(br.get('unhashed_user_data_params'))))
    if re.search(r'lcp|largest contentful', t) and br and br.get('lcp_ms'): v.append(('slow LCP', 'MEASURED', f"lcp={round(br['lcp_ms'])}ms from THIS network (compare with report value)"))
    if re.search(r'ttfb|server response', t): v.append(('slow TTFB', 'MEASURED', f"static={ (s or {}).get('ttfb_ms') }ms browser={((br or {}).get('perf') or {}).get('ttfb_ms')}"))
    if re.search(r'tap|touch target', t) and br: v.append(('small tap targets', 'MEASURED', str(br.get('small_tap_targets'))))
    return v or [('(claim type not auto-checkable)', 'MANUAL', '')]
res = {'sites': [], 'adlib': []}
for host, url in pick_urls():
    s = static_check(url); br = None
    if use_browser:
        try: br = browser_check(url)
        except Exception as e: br = {'error': 'playwright unavailable: ' + repr(e)[:150]}
    verdicts = []
    for l in probe['leaks']:
        if host in l['text'].lower() or host.replace('www.', '') in l['text'].lower():
            for claim, verdict, why in judge(l['text'], s, br): verdicts.append({'leak': l['label'], 'severity': l['severity'], 'claim': claim, 'verdict': verdict, 'why': why})
    res['sites'].append({'host': host, 'static': s, 'browser': br, 'verdicts': verdicts}); print('verified', host, s.get('status'), s.get('error', ''))
if use_browser and probe['ad_ids']:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True); pg = b.new_page(user_agent=UA)
        for aid in probe['ad_ids'][:15]:
            try:
                pg.goto(f'https://www.facebook.com/ads/library/?id={aid}', timeout=30000); pg.wait_for_timeout(5000)
                txt = pg.inner_text('body')[:6000]
                st = 'FOUND' if aid in txt else ('BLOCKED/LOGIN-OR-CONSENT-WALL' if re.search(r'log in|cookies|consent', txt, re.I) else 'NOT_FOUND')
            except Exception as e: st = 'ERROR ' + repr(e)[:80]
            res['adlib'].append({'ad_id': aid, 'status': st})
        b.close()
json.dump(res, open(out_p, 'w'), indent=1)
