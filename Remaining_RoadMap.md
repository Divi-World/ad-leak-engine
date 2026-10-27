Scale swarm to 10 shards (Phase 7 gate)
Implement 10 missing detection signals (Section 6)
Create missing orchestrator routes (scan.py, leads.py, health.py, feedback.py)
Build orchestrator/scheduler.py for scan scheduling
Build self_heal/retry_policy.py with backoff strategies
Build self_heal/health_monitor.py for metrics collection
Build shared/user_agents.py for UA rotation
Build shared/metrics.py for counter collection
Build persistence/cache.py with TTL strategy
Build persistence/storage.py for evidence storage
Create scripts/export_leads.sh
Implement TLS fingerprint randomization
Implement header randomization
Verify nightly scan workflow
Run 100 concurrent scan load test
Verify 1,000-page gate
Generate API documentation
Implement fix effectiveness tracking (30-day re-scan)





🚀 STEP-BY-STEP IMPLEMENTATION PLAN (Pre-Deployment)
To elevate this system to a Top 1 Service and justify an $80k–$200k valuation before adding user auth or payments, execute these steps in exact order.
Phase 1: Eliminate Polling & Polish Code (Week 1)
Action 1.1: Remove the 8 unused imports identified by Pylint to achieve a perfect 10/10 score.
Action 1.2: Implement Server-Sent Events (SSE) in src/ad_leak_engine/orchestrator/routes/api.py.
Command: Create a new endpoint @router.get("/api/v1/scan/stream/{job_id}") that yields JSON status updates as the swarm dispatcher processes each page.
Result: Frontend switches from setInterval polling to a single EventSource connection. Zero unnecessary HTTP requests.
Phase 2: Reframe Financials for "Top 1" Credibility (Week 1)
Action: The system honestly uses heuristics when the Meta API is unavailable. Do not remove this; it is a valuable fallback. However, rebrand the output.
Implementation: In src/ad_leak_engine/orchestrator/routes/api.py and outreach/bundle.py, change the output string from "heuristic" to "benchmark_estimated".
Result: Maintains technical honesty while presenting the data as professional, agency-grade intelligence rather than a "guess."
Phase 3: Prove Live Scraping in CI/CD (Week 2)
Action: The system must prove it can bypass bot detection in a production environment.
Implementation: Create .github/workflows/ci.yml. Configure it to run pytest --run-live. Inject residential proxy credentials (e.g., BrightData or Smartproxy) via GitHub Secrets (${{ secrets.PROXY_URL }}).
Result: Provides undeniable, automated proof to any acquirer that the scraping engine is robust and not just a local mock.
Phase 4: Introduce Multi-Tenant State Management (Week 3)
Action: Decouple the scraping workload from the API response to handle concurrent users.
Implementation:
Add redis and celery to requirements.txt.
Create src/ad_leak_engine/orchestrator/tasks.py to handle the trigger_scan logic asynchronously.
Store final job states and file paths (output/{uuid}/teardown.md) in a lightweight SQLite database (via SQLAlchemy) instead of relying solely on the file system.
Result: The system can now handle 50+ concurrent audits without blocking the API or mixing up job IDs.







PHASE 5: INTELLIGENCE DEPTH & DIRECT AUDIT ENGINE
Goal: Maximize email capture rate, deepen fix specificity for modern stacks, and enable direct URL/ID auditing.
5.1 Aggressive Email Discovery Integration
Objective: Lift Tier 1 email hit rate from ~40% to >80%.
Action:
Integrate shared/email_discovery.py (created earlier) fully into orchestrator/routes/api.py.
Implement Sitemap-Aware Contact Crawler: Fetch /sitemap.xml, parse for /contact, /about, /team, /leadership.
Implement Deep Page Probing: Stealth-fetch these discovered URLs using existing _fetch_html_resilient / Playwright stack.
Extract emails via Regex + JSON-LD + Mailto links from all probed pages, not just landing page.
Feed all candidates into select_best_email() for final scoring.
5.2 Headless & Enterprise Fix Generators
Objective: Provide actionable code for Next.js, Vercel, Sitecore, Adobe Experience Manager.
Action:
Extend fix_forge/platforms/ with new modules:
nextjs_headless.py: Generates useEffect hooks or _app.tsx modifications for Meta Pixel initialization on hydration. Includes Server-Side Rendering (SSR) safe patterns.
sitecore_aem.py: Generates generic GTM container injection snippets suitable for enterprise tag managers used by Sitecore/AEM implementations.
Update platform_fingerprint/detector.py to recognize Next.js markers (__NEXT_DATA__, vercel.app) and Enterprise CMS headers.
Route detected platforms to specific fix generators.
5.3 Direct Audit API Endpoint
Objective: Allow users to audit any website/page ID instantly without keyword search.
Action:
Add new endpoint: POST /api/v1/audit/direct.
Payload: { "url": "https://example.com", "page_id": "optional_fb_page_id" }.
Logic:
If url provided: Skip Ad Library discovery. Go straight to L2/L3 scanning of that URL.
If page_id provided: Use existing competitor/ad library logic to fetch ads for that specific page, then scan landing pages.
Merge results into standard OutreachPack format.
Frontend UI: Add "Direct Audit" tab/input field.
PHASE 6: VISUAL POLISH & REPORTING SUITE
Goal: Transform raw data into compelling, sales-ready visual assets.
6.1 HTML Report Generator
Objective: Replace Markdown teardowns with styled, interactive HTML reports.
Action:
Create Jinja2 template report.html.j2.
Include CSS framework (Tailwind or Bootstrap) for professional look.
Visual Elements:
Severity Heatmap: Color-coded badges (Red/Orange/Yellow/Green).
Financial Impact Chart: Bar chart comparing "Current Estimated Loss" vs. "Post-Fix Recovery."
Competitor Benchmark Graph: Radar or bar chart showing prospect vs. top competitors' ad volume/spend (if available).
Code Snippet Viewer: Syntax-highlighted blocks for fixes (Prism.js or Highlight.js).
Export functionality: Generate PDF from HTML using WeasyPrint or Playwright PDF rendering.
6.2 Executive Summary Refinement
Objective: Make the first 3 seconds count for busy executives.
Action:
Enhance message_gen.py to produce a "One-Pager" executive summary at the top of every report.
Key metrics bolded: Total Leaks Found, Est. Monthly Revenue Loss, Top Priority Fix.
Tone adjustment: More consultative, less robotic. "Here is exactly where you are bleeding money..."
PHASE 7: INFRASTRUCTURE, AUTH & BILLING (COMMERCIALIZATION)
Goal: Deploy as a secure, multi-tenant SaaS product.
(This is essentially the old Phase 5, moved down)
7.1 Dockerization & Orchestration
Containerize Uvicorn, Celery Worker, Redis, Postgres.
docker-compose.yml for dev/prod parity.
Environment variable management for secrets.
7.2 Database Migration (SQLite → PostgreSQL)
Async SQLAlchemy setup.
Tenant isolation schema (tenant_id foreign keys everywhere).
Migration scripts.
7.3 Authentication & Authorization
NextAuth/Clerk integration for frontend.
JWT middleware for backend API protection.
RBAC: Admin, Agency User, Single Seat User.
7.4 Billing Integration (Stripe)
Product tiers: Starter, Pro, Enterprise.
Credit-based system (1 scan = 1 credit).
Webhooks for payment success/failure -> update DB quota.
7.5 Outreach Automation & Domain Setup
Connect Resend/SendGrid for automated email dispatch.
Configure SPF/DKIM/DMARC for adleakengine.com.
Unsubscribe/opt-out compliance handling.