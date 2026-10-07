# ALE audit bundle 20261007_010635
- repo root: C:/Users/USER/Documents/Projects/Ad-Leak-Engine
- python: Python 3.12.10
- api: http://127.0.0.1:8000
- tunnel: https://vjqw5lpk-3000.uks1.devtunnels.ms
- ids: c4c6eed1-e611-4190-89b6-68bc191d8118,08e25c4e-302a-4baf-845a-1286371036b5
- git head: 55a1cc3c152faefe4a4f34e57cc8db2c35c65a5b  branch: main
- os: MINGW64_NT-10.0-22621 DESKTOP-HT764P6 3.3.4-341.x86_64 2022-05-09 11:56 UTC x86_64 Msys

## Test result
======================= 116 passed, 3 skipped in 57.72s =======================
src\ad_leak_engine\orchestrator\scheduler.py                             2      2     0%   2-3
src\ad_leak_engine\outreach\__init__.py                                  0      0   100%
src\ad_leak_engine\outreach\bundle.py                                   70     19    73%   85-91, 95-103, 113-121
src\ad_leak_engine\outreach\compliance.py                               11      1    91%   24
src\ad_leak_engine\outreach\dispatcher.py                               16     16     0%   2-31
src\ad_leak_engine\outreach\message_gen.py                              58     30    48%   45-46, 48, 51-77
src\ad_leak_engine\persistence\__init__.py                               0      0   100%
src\ad_leak_engine\persistence\cache.py                                  8      0   100%
src\ad_leak_engine\persistence\connection_pool.py                       10     10     0%   4-20
src\ad_leak_engine\persistence\db.py                                    10     10     0%   2-17
src\ad_leak_engine\persistence\models.py                                18     18     0%   2-26
src\ad_leak_engine\persistence\repository.py                            24     24     0%   2-42
src\ad_leak_engine\persistence\storage.py                                8      8     0%   2-9
src\ad_leak_engine\platform_fingerprint\__init__.py                      0      0   100%
src\ad_leak_engine\platform_fingerprint\confidence.py                   11      0   100%
src\ad_leak_engine\platform_fingerprint\detector.py                     51      2    96%   61-62
src\ad_leak_engine\platform_fingerprint\signatures.py                    3      0   100%
src\ad_leak_engine\self_heal\__init__.py                                 0      0   100%
src\ad_leak_engine\self_heal\circuit_breaker.py                         32      3    91%   36-38
src\ad_leak_engine\self_heal\fallback_chain.py                          46     34    26%   35-74
src\ad_leak_engine\self_heal\health_monitor.py                           6      0   100%
src\ad_leak_engine\self_heal\human_browser.py                           61     31    49%   38-45, 56-67, 71-94
src\ad_leak_engine\self_heal\proxy_manager.py                           75      9    88%   49-50, 55, 60, 68-71, 92
src\ad_leak_engine\self_heal\retry_policy.py                             7      1    86%   5
src\ad_leak_engine\self_heal\schema_drift.py                            16     16     0%   2-21
src\ad_leak_engine\self_improve\__init__.py                              0      0   100%
src\ad_leak_engine\self_improve\effectiveness.py                        12     12     0%   4-21
src\ad_leak_engine\self_improve\niche.py                                14     14     0%   2-20
src\ad_leak_engine\self_improve\tracker.py                              19      2    89%   14, 33
src\ad_leak_engine\self_improve\weights.py                              13      0   100%
src\ad_leak_engine\shared\__init__.py                                    0      0   100%
src\ad_leak_engine\shared\advanced_headers.py                            6      4    33%   8-12
src\ad_leak_engine\shared\constants.py                                  17      0   100%
src\ad_leak_engine\shared\exceptions.py                                  9      0   100%
src\ad_leak_engine\shared\interfaces.py                                 24      0   100%
src\ad_leak_engine\shared\logging.py                                    22     22     0%   2-39
src\ad_leak_engine\shared\metrics.py                                     5      5     0%   2-6
src\ad_leak_engine\shared\schemas.py                                    86      0   100%
src\ad_leak_engine\shared\user_agents.py                                 4      4     0%   2-8
TOTAL                                                                 2441   1410    42%

## Evidence coverage (engine's own leaks that carry any evidence field)
05_probe_08e25c4e.json {'with_evidence': 0, 'total_leaks': 0} sites: 0 ad_ids: 0 claims: 13
05_probe_c4c6eed1.json {'with_evidence': 0, 'total_leaks': 0} sites: 1 ad_ids: 0 claims: 13

## Verdict tally per scan
06_verify_08e25c4e.json claims: {} | ad library: {}
06_verify_c4c6eed1.json claims: {} | ad library: {}

## Files
C:/Users/USER/Documents/Projects/Ad-Leak-Engine/ale_audit_20261007_010635/raw:
api_api_v1_scan_status_job_id_08e25c4e.json
api_api_v1_scan_status_job_id_c4c6eed1.json
artefact_copies
artefacts.txt
config
cors_evil.hdr
cors_headers.txt
env_key_names.txt
frontend_api_refs.txt
frontend_pkg.txt
git_log.txt
git_status.txt
gitignore.txt
jobs.json
openapi.json
report_08e25c4e.json
report_c4c6eed1.json
src_dirs.txt
tracked_files.txt
tracked_sensitive_names.txt

C:/Users/USER/Documents/Projects/Ad-Leak-Engine/ale_audit_20261007_010635/reports:
01_repo_intel.md
04_pdf_text.md
05_probe_08e25c4e.json
05_probe_c4c6eed1.json
06_verify_08e25c4e.json
06_verify_c4c6eed1.json
07_tunnel.md
