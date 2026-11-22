# Ad-Leak-Engine — Engineering Ledger [SEED: 2399]
Every item traceable to a read or a log line. No speculative entries.
Rule: rewire only what is superior and unused; never remove working behaviour.

## P0 — Capability delivery
| ID | Item | Evidence | Status |
|----|------|----------|--------|
| L1 | TIER 6 gate `escalate = force_ecommerce or _looks_like_ecommerce(url)` hides funnel from frontend | l2_probe:4295 + Celery log has no "Escalating" line | OPEN — resolves via L2 |
| L2 | Detector lacked enterprise markers, minified JSON-LD, /basket path | marker list read; JSON-LD proof `minified hit: False` | PARTIAL — markers+paths+headers+stub applied; still returns False |
| L3 | Email asset filter tested `local` not `domain` | validator body; `photo_600x600@2x.jpg` passed | CLOSED — EMAIL_FILTER_OK |
| L42 | Detector cannot distinguish fetch-failure from not-commerce; `except: logger.debug` | three silent `return False` paths | OPEN |

## P1 — Proven silent failures
| ID | Item | Evidence |
|----|------|----------|
| L4 | Weights file collision: weights.py L1/L2/L3 vs effectiveness template_multipliers, same path | on-disk keys ['L1','L2','L3']; KeyError reproduced |
| L5 | L2 weight vocabulary 0/4 match emitted signals (L1 4/4, L3 4/4) | DEFAULT_WEIGHTS vs signal inventory |
| L6 | Both weight stores write-only, zero consumers | consumer grep |
| L7 | `calculate_priority_score` never called | grep: definition only |
| L8 | `currency` hardcoded "USD" while account currency fetched | graph_financial return dict |
| L9 | `purchase_roas` structured field -> float() TypeError swallowed | Meta docs structured field |
| L10 | `count_ads()` loads every row to count | repository body |
| L11 | 10-shard matrix passes no shard identity -> 10x duplicate work | swarm_matrix.yml + swarm_scrape args |

## P2 — Disconnected assets (judge each on merit)
| ID | Item | Note |
|----|------|------|
| L12 | HybridRouter | KEYSTONE — revives circuit_breaker, fallback_chain, health_monitor, retry_policy, schema_drift |
| L13 | SwarmProxyManager | fleet pacing/cooldown, superior unused |
| L14 | SwarmDispatcher | plan_batches solves L11; estimate_runner_load free-tier budget |
| L15 | GraphQLConnectionPool | TLS reuse; per-request timeout preserved |
| L16 | Settings never loaded; db_url duplicates DB_PATH | two config mechanisms |
| L17 | MultiPageCrawler, PixelProbe | L3 sub-scanners unused |
| L18 | AdLibraryAPISource, AdLibraryFieldMapper, Deduplicator, parse_html_to_ads, SessionHandshake | ingest alternates |
| L19 | detect_cms, get_fix_context, validate_fix | CMS + fix validation |
| L20 | detect_no_retargeting | L1 detector |
| L21 | stealth_fetch, get_random_ua, ManagedTorClient, Metrics, CAPTCHAError, ProxyDeadError | shared/utils |
| L22 | EvidenceStorage | LEAVE — no producer exists |
| L23 | schedule_nightly_scan | pass stub |
| L24 | routes/health.py | LEAVE — app.py probe is richer |

## P3 — Capability and product
| ID | Item |
|----|------|
| L25 | Non-ecommerce lead-flow actor (51 verticals, most have no basket) |
| L26 | cmd_feedback four hardcodes: 0.8, 0.4/0.9, "template_id", "ecommerce" |
| L27 | template_multipliers has no real key; Fix schema has no template_id |
| L28 | ROAS_VALIDATION_THRESHOLD / CPA_DEVIATION_ALERT unused |
| L29 | Page.last_scanned declared, never written |
| L30 | TENANT_RBAC_SCOPES (6 scopes) unused |
| L31 | Zero inbound auth; CORS comment declares X-API-Key intent |
| L32 | Tenancy hardcoded seed_2399; AdRecord has no tenant_id |
| L33 | No ScanJob/LeakRecord/ScanHistory; create_all will not add columns |
| L34 | No beat schedule; CI scrapes only, never audits |
| L35 | Frontend missing the new captures |
| L36 | 766-term expansion map duplicated in two files (in sync today) |
| L37 | Breadth harness is synthetic L1-only |
| L38 | Load harness is synthetic with sleep() |
| L39 | 143s sequential tag phase; recovery model saturates at 50% cap |
| L40 | History purge of ale_audit_* + IDs in 53d7457 — OWNER DECISION |
| L41 | .gitignore prose, pyproject.toml wrongly ignored, investigation dirs |

## Closed and pushed
- Tenant import -> financial read path restored (8787793)
- Tag-fetch retry + full outcome ledger + consent breadth + full teardown ledger (634dc87)
- NOCAND reachability, gtag IDs, dual scan contract (f1bb6b9)
- Census, per-pixel verdicts, dormancy grading, guest discovery (earlier commits)

## Execution order
P0 (L1,L2,L3,L42) -> P1 (L4-L11) -> P2 (L12-L24, HybridRouter first) -> P3 (L25-L39) -> L40/L41 decisions
