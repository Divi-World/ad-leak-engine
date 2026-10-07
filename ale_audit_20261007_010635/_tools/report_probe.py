import json, sys, re, collections
from urllib.parse import urlparse
src = sys.argv[1]
data = json.load(open(src, encoding='utf-8'))
def walk(o, path=''):
    yield path, o
    if isinstance(o, dict):
        for k, v in o.items(): yield from walk(v, f'{path}.{k}' if path else k)
    elif isinstance(o, list):
        for v in o[:2000]: yield from walk(v, path + '[]')
schema = collections.OrderedDict(); urls = set(); adids = set(); leaks = []; claims = []
MONEY = re.compile(r'(?:[$€£]\s?\d[\d,\.]*\s?[kKmM]?\b|\b\d[\d,\.]*\s?(?:USD|EUR|GBP)\b)')
PCT = re.compile(r'\b\d+(?:\.\d+)?\s?%')
URL = re.compile(r'https?://[^\s"\'<>\)\]]+')
EVID = re.compile(r'evidence|proof|screenshot|snapshot|har|trace|selector|request|raw|source|observed|detected_by|rule', re.I)
for path, v in walk(data):
    t = type(v).__name__
    schema.setdefault(path or '$', collections.Counter())[t] += 1
    if isinstance(v, str):
        for u in URL.findall(v): urls.add(u.rstrip('.,;'))
        for rx, kind in ((MONEY, 'money'), (PCT, 'percent')):
            for m in rx.finditer(v):
                claims.append({'path': path, 'kind': kind, 'value': m.group(0), 'context': v[max(0, m.start()-70):m.end()+70].replace('\n', ' ')})
    if isinstance(v, dict):
        for k, x in v.items():
            if re.fullmatch(r'(?i)(ad_?id|ad_archive_id|archive_id|library_id)', k) and x: adids.add(str(x))
        keys = set(v.keys())
        if 'severity' in keys and (keys & {'type', 'leak_type', 'category', 'title', 'id', 'leak_id'}):
            ev = {k: v[k] for k in keys if EVID.search(k)}
            nonempty = {k: x for k, x in ev.items() if x not in (None, '', [], {}, 0)}
            leaks.append({'path': path, 'keys': sorted(keys), 'evidence_keys': sorted(ev), 'evidence_nonempty_keys': sorted(nonempty),
                          'has_evidence': bool(nonempty), 'severity': v.get('severity'),
                          'label': str(v.get('type') or v.get('leak_type') or v.get('title') or v.get('id'))[:80],
                          'text': json.dumps(v, default=str)[:1500]})
skip = ('facebook.com', 'fbcdn.net', 'fb.com', 'instagram.com', 'fbsbx.com')
sites = sorted({urlparse(u).netloc.lower() for u in urls if urlparse(u).netloc and not any(urlparse(u).netloc.lower().endswith(s) for s in skip)})
cov = (sum(1 for l in leaks if l['has_evidence']), len(leaks))
out = {'source': src, 'top_level_keys': list(data.keys()) if isinstance(data, dict) else 'list',
       'schema': {k: dict(v) for k, v in schema.items()}, 'urls': sorted(urls), 'sites': sites,
       'ad_ids': sorted(adids), 'leaks': leaks, 'evidence_coverage': {'with_evidence': cov[0], 'total_leaks': cov[1]},
       'claims': claims}
json.dump(out, open(sys.argv[2], 'w'), indent=1)
print(f'{src}: leaks={cov[1]} with_evidence={cov[0]} sites={len(sites)} ad_ids={len(adids)} money/pct claims={len(claims)}')
