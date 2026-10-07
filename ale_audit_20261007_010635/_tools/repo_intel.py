import ast, os, re, sys, json, collections
root = sys.argv[1]
SKIP = {'.git','.venv','venv','node_modules','.next','__pycache__','.pytest_cache','dist','build','.mypy_cache'}
files = []
for d, ds, fs in os.walk(root):
    ds[:] = [x for x in ds if x not in SKIP and not x.startswith('ale_audit_')]
    for f in fs: files.append(os.path.join(d, f))
def rel(p): return os.path.relpath(p, root).replace('\\','/')
def read(p):
    try: return open(p, encoding='utf-8', errors='ignore').read()
    except Exception: return ''
loc = collections.Counter(); cnt = collections.Counter()
for p in files:
    ext = os.path.splitext(p)[1].lower() or '(none)'
    t = read(p)
    if ext in ('.py','.ts','.tsx','.js','.jsx','.sh','.md','.json','.yml','.yaml','.toml','.html','.css','.liquid','.php'):
        loc[ext] += t.count('\n') + 1; cnt[ext] += 1
src_py = [p for p in files if p.endswith('.py') and '/tests/' not in rel(p).replace('\\','/') + '/' and not rel(p).startswith('tests/')]
test_py = [p for p in files if p.endswith('.py') and (rel(p).startswith('tests/') or '/tests/' in rel(p))]
ROUTE = re.compile(r'@\s*(\w+)\.(get|post|put|delete|patch|websocket)\(\s*[rf]?["\']([^"\']+)')
INCL = re.compile(r'include_router\(([^)]*)\)')
ENV = re.compile(r'(?:getenv|environ(?:\.get)?)\s*[\(\[]\s*["\']([A-Z0-9_]+)')
SUS = re.compile(r'\b(random\.|uuid4\(|TODO|FIXME|HACK|XXX|NotImplemented|placeholder|dummy|mock|fake|hardcod|stub|simulate|assum|heuristic|estimate)', re.I)
LLM = re.compile(r'\b(anthropic|openai|google\.generativeai|genai|groq|mistral|ollama|litellm|langchain|llama)\b', re.I)
NET = re.compile(r'\b(httpx|requests|aiohttp|playwright|selenium|urllib|curl_cffi|scrapy|undetected|proxy|proxies)\b', re.I)
SECRET = [('private_key', r'-----BEGIN [A-Z ]*PRIVATE KEY-----'), ('anthropic/openai', r'sk-[A-Za-z0-9_\-]{20,}'),
          ('google_key', r'AIza[0-9A-Za-z_\-]{35}'), ('meta_token', r'EAA[0-9A-Za-z]{30,}'), ('github', r'ghp_[A-Za-z0-9]{30,}'),
          ('generic_assign', r'(?i)(api[_-]?key|secret|token|passwd|password)\s*[:=]\s*["\'][^"\']{12,}["\']')]
routes, envs, sus, llm, net, secrets = [], collections.defaultdict(set), [], collections.defaultdict(set), collections.defaultdict(set), []
funcs = classes = nodoc = bare_exc = stub_funcs = 0
big = []; parse_err = []
for p in src_py + test_py:
    t = read(p); r = rel(p)
    for i, line in enumerate(t.splitlines(), 1):
        for kind, rx in SECRET:
            if re.search(rx, line): secrets.append(f'{r}:{i}:{kind}')
    if p in test_py: continue
    for m in ROUTE.finditer(t): routes.append((r, m.group(2).upper(), m.group(3)))
    for m in INCL.finditer(t): routes.append((r, 'INCLUDE', m.group(1).strip()))
    for m in ENV.finditer(t): envs[m.group(1)].add(r)
    for m in LLM.finditer(t): llm[m.group(1).lower()].add(r)
    for m in NET.finditer(t): net[m.group(1).lower()].add(r)
    for i, line in enumerate(t.splitlines(), 1):
        m = SUS.search(line)
        if m: sus.append(f'{r}:{i}:{m.group(1).lower()}: {line.strip()[:110]}')
    try: tree = ast.parse(t)
    except SyntaxError as e: parse_err.append(f'{r}: {e}'); continue
    big.append((t.count('\n'), r))
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs += 1
            if not ast.get_docstring(n): nodoc += 1
            body = [b for b in n.body if not (isinstance(b, ast.Expr) and isinstance(getattr(b,'value',None), ast.Constant))]
            if len(body) == 1 and isinstance(body[0], (ast.Pass, ast.Raise)): stub_funcs += 1
        elif isinstance(n, ast.ClassDef): classes += 1
        elif isinstance(n, ast.ExceptHandler) and n.type is None: bare_exc += 1
out = []
P = out.append
P('## 1. Code inventory\n')
P('| ext | files | lines |\n|---|---|---|')
for e, l in loc.most_common(): P(f'| {e} | {cnt[e]} | {l} |')
P(f'\n- python source files: {len(src_py)}, python test files: {len(test_py)}')
P(f'- functions: {funcs}, classes: {classes}, functions without docstring: {nodoc}, stub-only functions (pass/raise): {stub_funcs}, bare `except:` {bare_exc}')
P(f'- syntax/parse errors: {len(parse_err)} {parse_err[:5]}')
P('\n### Largest python files\n'); [P(f'- {n} lines  {f}') for n, f in sorted(big, reverse=True)[:12]]
P('\n## 2. HTTP surface found in source (decorators)\n')
for r, m, pth in sorted(set(routes)): P(f'- `{m} {pth}`  ({r})')
P('\n## 3. Environment variables read by code (names only)\n')
for k in sorted(envs): P(f'- `{k}`  <- {", ".join(sorted(envs[k]))[:140]}')
P('\n## 4. LLM / AI providers referenced\n'); [P(f'- {k}: {sorted(v)[:5]}') for k, v in sorted(llm.items())] or P('- none found')
P('\n## 5. Network / scraping libraries referenced\n'); [P(f'- {k}: {len(v)} files') for k, v in sorted(net.items())]
P(f'\n## 6. Risk-marker lines in NON-test source ({len(sus)} total, first 120)\n')
for s in sus[:120]: P(f'- {s}')
P(f'\n## 7. Possible hard-coded secrets (location only, values never printed): {len(secrets)}\n')
for s in secrets[:40]: P(f'- {s}')
P('\n## 8. Test mapping\n')
srcmods = {os.path.splitext(os.path.basename(p))[0] for p in src_py if not p.endswith('__init__.py')}
tested = {m for m in srcmods if any(m in read(t) for t in test_py)}
P(f'- source modules: {len(srcmods)}; referenced by at least one test file: {len(tested)}')
P('- modules with NO test reference: ' + ', '.join(sorted(srcmods - tested)))
print('\n'.join(out))
