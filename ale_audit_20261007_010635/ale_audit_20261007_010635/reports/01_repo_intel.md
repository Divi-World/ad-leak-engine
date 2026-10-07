## 1. Code inventory

| ext | files | lines |
|---|---|---|
| .md | 397 | 153420 |
| .json | 158 | 13590 |
| .py | 128 | 6611 |
| .sh | 16 | 1255 |
| .tsx | 2 | 484 |
| .html | 5 | 285 |
| .yml | 3 | 104 |
| .css | 1 | 84 |
| .toml | 1 | 41 |
| .ts | 2 | 16 |

- python source files: 101, python test files: 27
- functions: 245, classes: 77, functions without docstring: 181, stub-only functions (pass/raise): 4, bare `except:` 0
- syntax/parse errors: 1 ['scripts/apply_patch.py: unterminated triple-quoted string literal (detected at line 260) (<unknown>, line 224)']

### Largest python files

- 528 lines  src/ad_leak_engine/orchestrator/routes/api.py
- 257 lines  src/ad_leak_engine/cli.py
- 160 lines  src/ad_leak_engine/fix_forge/platforms/shopify.py
- 155 lines  src/ad_leak_engine/fix_forge/platforms/custom.py
- 150 lines  src/ad_leak_engine/fix_forge/platforms/woocommerce.py
- 130 lines  src/ad_leak_engine/intelligence/competitor.py
- 124 lines  src/ad_leak_engine/ingest/graph_financial.py
- 121 lines  src/ad_leak_engine/outreach/bundle.py
- 118 lines  src/ad_leak_engine/fix_forge/platforms/bigcommerce.py
- 113 lines  src/ad_leak_engine/shared/schemas.py
- 113 lines  src/ad_leak_engine/leak_scan/l2_probe.py
- 109 lines  audit_system.py

## 2. HTTP surface found in source (decorators)

- `GET /health`  (src/ad_leak_engine/orchestrator/app.py)
- `INCLUDE api.router, prefix="/api/v1", tags=["Frontend API"]`  (src/ad_leak_engine/orchestrator/app.py)
- `INCLUDE feedback.router`  (src/ad_leak_engine/orchestrator/app.py)
- `INCLUDE leads.router`  (src/ad_leak_engine/orchestrator/app.py)
- `INCLUDE oauth.router, prefix="/api/v1", tags=["OAuth"]`  (src/ad_leak_engine/orchestrator/app.py)
- `INCLUDE scan.router`  (src/ad_leak_engine/orchestrator/app.py)
- `GET /jobs`  (src/ad_leak_engine/orchestrator/routes/api.py)
- `GET /report/{job_id}/{page_id}`  (src/ad_leak_engine/orchestrator/routes/api.py)
- `GET /report/{job_id}/{page_id}/pdf`  (src/ad_leak_engine/orchestrator/routes/api.py)
- `GET /scan/status/{job_id}`  (src/ad_leak_engine/orchestrator/routes/api.py)
- `POST /outreach/send`  (src/ad_leak_engine/orchestrator/routes/api.py)
- `POST /scan/trigger`  (src/ad_leak_engine/orchestrator/routes/api.py)
- `POST /feedback/reply`  (src/ad_leak_engine/orchestrator/routes/feedback.py)
- `GET /health`  (src/ad_leak_engine/orchestrator/routes/health.py)
- `GET /leads`  (src/ad_leak_engine/orchestrator/routes/leads.py)
- `GET /meta/callback`  (src/ad_leak_engine/orchestrator/routes/oauth.py)
- `GET /meta/login`  (src/ad_leak_engine/orchestrator/routes/oauth.py)
- `POST /scan`  (src/ad_leak_engine/orchestrator/routes/scan.py)

## 3. Environment variables read by code (names only)

- `DB_PATH`  <- src/ad_leak_engine/persistence/db.py
- `FROM_EMAIL`  <- src/ad_leak_engine/outreach/dispatcher.py
- `META_AD_LIBRARY_TOKEN`  <- src/ad_leak_engine/ingest/api_source.py
- `META_APP_ID`  <- src/ad_leak_engine/orchestrator/routes/oauth.py
- `META_APP_SECRET`  <- src/ad_leak_engine/orchestrator/routes/oauth.py
- `META_REDIRECT_URI`  <- src/ad_leak_engine/orchestrator/routes/oauth.py
- `PYTHONIOENCODING`  <- scripts/apply_patch.py, src/ad_leak_engine/cli.py
- `RESEND_API_KEY`  <- src/ad_leak_engine/outreach/dispatcher.py

## 4. LLM / AI providers referenced

- none found

## 5. Network / scraping libraries referenced

- curl_cffi: 6 files
- httpx: 7 files
- playwright: 10 files
- proxy: 1 files
- requests: 12 files
- urllib: 4 files

## 6. Risk-marker lines in NON-test source (47 total, first 120)

- audit_system.py:84:stub: # Check for Orphaned/Stub Files
- audit_system.py:86:stub: print("  ORPHANED / STUB FILE CHECK")
- audit_system.py:99:stub: print(f"[-] DEAD STUB: {orphan} (No functions/classes defined)")
- scripts/apply_patch.py:104:estimate: print(f"[ALE]   -> Estimated recovery: {pack.estimated_recovery}")
- scripts/load_test.py:15:mock: # Mock a page with 5 ads to test the internal pipeline concurrency
- scripts/load_test.py:20:simulate: # Simulate async work
- scripts/verify_1000_pages.py:2:simulate: Simulates processing 1,000 pages to verify zero data loss and pipeline completion.
- src/ad_leak_engine/cli.py:208:estimate: print(f"[ALE]   -> Estimated recovery: {pack.estimated_recovery}")
- src/ad_leak_engine/config/enterprise_scopes.py:24:estimate: # Financial Validation Thresholds (Used to replace 'estimated' spend with 'hard' proof)
- src/ad_leak_engine/ingest/graph_financial.py:4:heuristic: Falls back to enhanced heuristics when no token is available.
- src/ad_leak_engine/ingest/graph_financial.py:113:heuristic: Returns None if no OAuth token is available (falls back to heuristics).
- src/ad_leak_engine/ingest/playwright_source.py:22:hack: "marketing": ["seo", "agency", "digital marketing", "consulting", "b2b", "lead generation", "smm", "ppc", "gro
- src/ad_leak_engine/intelligence/competitor.py:18:dummy: self.token = [REDACTED] or "dummy_token_for_public_search"
- src/ad_leak_engine/leak_scan/l1_creative.py:85:heuristic: # Heuristic: lacks specific geo or pain point
- src/ad_leak_engine/leak_scan/l1_creative.py:93:heuristic: # Heuristic: All ads target broad, no custom audience indicators in raw data
- src/ad_leak_engine/leak_scan/l1_creative.py:94:placeholder: return True # Placeholder for broad targeting heuristic
- src/ad_leak_engine/orchestrator/dispatcher.py:23:estimate: def estimate_runner_load(self, runs: int, shards_per_run: int = 5) -> dict:
- src/ad_leak_engine/orchestrator/dispatcher.py:24:estimate: """Estimate GitHub Actions minute usage against the free tier."""
- src/ad_leak_engine/orchestrator/dispatcher.py:30:estimate: "estimated_minutes": total_minutes,
- src/ad_leak_engine/orchestrator/routes/api.py:32:hardcod: # Replaces hardcoded keywords with real-time DOM/OG context analysis.
- src/ad_leak_engine/orchestrator/routes/api.py:146:hardcod: # Hardcoded locally to prevent cross-module import failures.
- src/ad_leak_engine/orchestrator/routes/api.py:164:hack: _digital_negatives = ["app", "apk", "download", "play store", "mod", "hack", "cheat", "free download", "instal
- src/ad_leak_engine/orchestrator/routes/api.py:372:heuristic: # [SEED: 2399] GRAPH API FINANCIAL INGESTION (Hard Data > Heuristics)
- src/ad_leak_engine/orchestrator/routes/api.py:402:estimate: "estimated_recovery": pack.estimated_recovery,
- src/ad_leak_engine/orchestrator/routes/api.py:403:heuristic: "financial_source": "meta_graph_api" if financial_data else "heuristic",
- src/ad_leak_engine/orchestrator/routes/api.py:421:uuid4(: job_id = str(uuid.uuid4())
- src/ad_leak_engine/outreach/bundle.py:35:estimate: estimated_recovery = self._estimate_recovery(page, leaks)
- src/ad_leak_engine/outreach/bundle.py:36:estimate: teardown_md = self._generate_teardown(page, leaks, fixes, estimated_recovery, financial_data=financial_data)
- src/ad_leak_engine/outreach/bundle.py:63:estimate: estimated_recovery=estimated_recovery,
- src/ad_leak_engine/outreach/bundle.py:66:estimate: def _generate_teardown(self, page: Page, leaks: list[Leak], fixes: list[Fix], estimated_recovery: str, financi
- src/ad_leak_engine/outreach/bundle.py:80:estimate: return template.render(page=page, leaks=leaks, fixes=fixes, estimated_recovery=estimated_recovery)
- src/ad_leak_engine/outreach/bundle.py:92:heuristic: # Fallback: enhanced heuristic estimation
- src/ad_leak_engine/outreach/bundle.py:105:estimate: # 2. FALLBACK: Meta Ad Library estimated spend range
- src/ad_leak_engine/self_heal/human_browser.py:30:random.: viewport = random.choices(VIEWPORTS, weights=VIEWPORT_WEIGHTS, k=1)[0]
- src/ad_leak_engine/self_heal/human_browser.py:31:random.: locale = random.choices(LOCALES, weights=LOCALE_WEIGHTS, k=1)[0]
- src/ad_leak_engine/self_heal/human_browser.py:51:random.: time.sleep(random.uniform(low, high))
- src/ad_leak_engine/self_heal/human_browser.py:67:random.: time.sleep(random.uniform(0.05, 0.15))
- src/ad_leak_engine/self_heal/proxy_manager.py:96:random.: return random.uniform(15.0, 45.0)
- src/ad_leak_engine/self_heal/retry_policy.py:5:random.: return (30 * (2 ** attempt)) + random.uniform(0, 5)
- src/ad_leak_engine/self_heal/retry_policy.py:7:random.: return (60 * (attempt + 1)) + random.uniform(0, 10)
- src/ad_leak_engine/shared/advanced_headers.py:9:random.: ver = random.choice(chrome_versions)
- src/ad_leak_engine/shared/advanced_headers.py:17:random.: "sec-fetch-mode": random.choice(["cors", "same-origin", "navigate"]),
- src/ad_leak_engine/shared/advanced_headers.py:18:random.: "sec-fetch-site": random.choice(["same-origin", "cross-site", "none"]),
- src/ad_leak_engine/shared/advanced_headers.py:19:random.: "accept-language": random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.9", "en;q=0.8"]),
- src/ad_leak_engine/shared/advanced_headers.py:20:random.: "priority": random.choice(["u=1, i", "u=0, i", "u=1"]),
- src/ad_leak_engine/shared/schemas.py:112:estimate: estimated_recovery: str
- src/ad_leak_engine/shared/user_agents.py:8:random.: return random.choice(USER_AGENTS)

## 7. Possible hard-coded secrets (location only, values never printed): 0


## 8. Test mapping

- source modules: 86; referenced by at least one test file: 39
- modules with NO test reference: advanced_headers, aggregate_swarm, api_interceptor, apply_patch, audit_system, cache, cart_analysis, cli, cms_detector, codegen, competitor, connection_pool, constants, crawler, effectiveness, enterprise_scopes, export_api_docs, extract_dossiers, fallback_chain, feedback, graph_financial, graphql_source, health_monitor, html_parser, interfaces, l2_probe, leads, load_test, logging, message_gen, metrics, mobile_ux, models, niche, oauth, pixel_probe, pricing_friction, repository, retry_policy, saas_waste, scheduler, session_handshake, signatures, storage, swarm_scrape, user_agents, verify_1000_pages
