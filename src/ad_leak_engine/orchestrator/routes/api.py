"""Frontend-facing API routes for Ad-Leak-Engine [SEED: 2399]."""
import os
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from ...ingest.playwright_source import PlaywrightSource
from ...leak_scan.l1_creative import L1CreativeScanner
from ...leak_scan.l2_tracking import L2TrackingScanner
from ...leak_scan.l3_scanner import L3SiteScanner
from ...platform_fingerprint.detector import PlatformDetector
from ...fix_forge.forge import FixForge
from ...outreach.bundle import OutreachBuilder
from ...persistence.db import init_db
from ...persistence.repository import AdRepository
from ...shared.schemas import Page
from ...shared.exceptions import PlatformAmbiguousError
from ...shared.logging import get_logger

router = APIRouter()
logger = get_logger()

def _write_status(job_id: str, payload: dict):
    with open(f"output/{job_id}/status.json", "w", encoding="utf-8") as _f:
        json.dump(payload, _f)

class ScanRequest(BaseModel):
    keyword: str
    country: str = "US"
    limit: int = 1

def run_scan_pipeline(job_id: str, keyword: str, country: str, limit: int):
    """Background task executing the proven scan pipeline."""
    init_db()
    repo = AdRepository()
    source = PlaywrightSource(headless=True)
    
    try:
        ads = list(source.search(keyword, country, max_results=50))
        if not ads:
            with open(f"output/{job_id}/status.json", "w") as f:
                json.dump({"status": "error", "message": "No ads found"}, f)
            return
            
        repo.upsert_ads(ads)
        _write_status(job_id, {"status": "running", "progress": 20, "stage": f"Extracted {len(ads)} live Meta ads. Grouping by page..."})

        by_page = {}
        for ad in ads:
            if ad.page_id not in by_page:
                by_page[ad.page_id] = []
            by_page[ad.page_id].append(ad)
            
        l1, l2, l3 = L1CreativeScanner(), L2TrackingScanner(), L3SiteScanner()
        detector, forge = PlatformDetector(), FixForge()
        builder = OutreachBuilder(output_dir=f"output/{job_id}")
        
        results = []
        processed = 0
        for page_id, page_ads in by_page.items():
            if processed >= limit:
                break
                
            page_name = page_ads[0].page_name
            landing = next((a.landing_url for a in page_ads if a.landing_url), None)
            page = Page(id=page_id, name=page_name, url=landing, ads=page_ads, first_seen=datetime.now(timezone.utc))
            _write_status(job_id, {"status": "running", "progress": min(95, 35 + int(50 * processed / max(limit, 1))), "stage": f"Auditing {page_name} ({processed + 1}/{limit}): L1 creative scan"})

            
            leaks = list(l1.scan(page))
            platform, conf, platform_evidence = "custom", 0.3, []
            html = None
            discovered_emails = []
            # [SEED: 2399] Define before first use; no cross-iteration state leak
            is_invalid = landing and (not landing.startswith(("http://", "https://")) or "fbgeo" in landing)
            if landing and not is_invalid:
                try:
                    from ...cli import _fetch_html_resilient
                    html = _fetch_html_resilient(landing)
                    if html:
                        platform, conf, platform_evidence = detector.detect(landing, html)
                        # [SEED: 2399] Contact Discovery
                        import re as _re_discover
                        raw_emails = _re_discover.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
                        discovered_emails = list(set([e for e in raw_emails if not e.lower().endswith(('.png', '.jpg', '.gif', '.svg', '.webp', '.js', '.css'))]))[:5]
                        _write_status(job_id, {"status": "running", "progress": min(95, 58 + int(50 * processed / max(limit, 1))), "stage": f"Auditing {page_name}: platform fingerprinted as {platform}"})

                except Exception:
                    pass
            
            # [SEED: 2399] Evidence snapshot reuse (shared store, 24h TTL) => bit-identical re-audits
            os.makedirs("output/_evidence", exist_ok=True)
            snapshot_path = f"output/_evidence/{page_id}.json"
            evidence_mode = "live"
            use_snapshot = False
            if os.path.exists(snapshot_path):
                import time as _time
                if _time.time() - os.path.getmtime(snapshot_path) < 86400:
                    try:
                        with open(snapshot_path, "r", encoding="utf-8") as sf:
                            page.raw = json.load(sf)
                        use_snapshot = True
                        evidence_mode = "snapshot"
                    except Exception:
                        pass
            if not use_snapshot and landing and not is_invalid:
                try:
                    from ...leak_scan.telemetry_collector import TelemetryCollector
                    page.raw = TelemetryCollector().collect(landing)
                    if html:
                        page.raw["html"] = html
                    with open(snapshot_path, "w", encoding="utf-8") as sf:
                        json.dump(page.raw, sf, default=str)
                    _write_status(job_id, {"status": "running", "progress": min(95, 45 + int(50 * processed / max(limit, 1))), "stage": f"Auditing {page_name}: L2/L3 telemetry captured (live)"})
                except Exception:
                    pass
            if page.raw:
                leaks += l2.scan(page) + l3.scan(page)
                    
                    
            fixes = []
            for leak in leaks:
                try:
                    fixes.append(forge.generate(leak, platform, conf))
                except PlatformAmbiguousError:
                    fixes.append(forge.generate(leak, "custom", conf))
                except Exception:
                    pass
                    
            pack = builder.build(page, leaks, fixes)
            _write_status(job_id, {"status": "running", "progress": min(95, 75 + int(20 * processed / max(limit, 1))), "stage": f"Auditing {page_name}: forging {platform} fixes & teardown"})

            results.append({
                "page_id": page_id,
                "page_name": page_name,
                "platform": platform,
                "confidence": conf,
                "leak_count": len(leaks),
                "estimated_recovery": pack.estimated_recovery,
                "teardown_path": f"output/{job_id}/{page_id}/teardown.md",
                "evidence_mode": evidence_mode,
                "platform_evidence": platform_evidence,
                "discovered_emails": discovered_emails
            })
            processed += 1
            
        with open(f"output/{job_id}/status.json", "w") as f:
            json.dump({"status": "completed", "results": results}, f)
            
    except Exception as e:
        with open(f"output/{job_id}/status.json", "w") as f:
            json.dump({"status": "error", "message": str(e)}, f)

@router.post("/scan/trigger")
async def trigger_scan(request: ScanRequest, background_tasks: BackgroundTasks) -> dict:
    job_id = str(uuid.uuid4())
    os.makedirs(f"output/{job_id}", exist_ok=True)
    with open(f"output/{job_id}/status.json", "w") as f:
        json.dump({"status": "pending", "progress": 0}, f)
        
    background_tasks.add_task(run_scan_pipeline, job_id, request.keyword, request.country, request.limit)
    return {"status": "accepted", "job_id": job_id, "message": "Scan initiated"}

@router.get("/jobs")
def list_jobs() -> dict:
    """[SEED: 2399] Scan history: recent jobs with status + results summaries."""
    base = Path("output")
    jobs = []
    if base.exists():
        for d in sorted(base.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if d.is_dir() and d.name != "_evidence":
                sf = d / "status.json"
                if sf.exists():
                    try:
                        with open(sf, "r", encoding="utf-8") as f:
                            st = json.load(f)
                        jobs.append({
                            "job_id": d.name,
                            "status": st.get("status", "unknown"),
                            "pages": len(st.get("results", [])),
                            "results": st.get("results", []),
                        })
                    except Exception:
                        continue
            if len(jobs) >= 20:
                break
    return {"status": "ok", "jobs": jobs}

@router.get("/scan/status/{job_id}")
def get_scan_status(job_id: str) -> dict:
    status_file = Path(f"output/{job_id}/status.json")
    if status_file.exists():
        with open(status_file, "r") as f:
            return json.load(f)
    return {"status": "not_found"}

@router.get("/report/{job_id}/{page_id}")
def get_report(job_id: str, page_id: str) -> dict:
    """Read the existing on-disk teardown and outreach message for a scanned page."""
    import re as _re
    if not _re.fullmatch(r"[0-9a-zA-Z\-]+", job_id) or not _re.fullmatch(r"[0-9a-zA-Z\-]+", page_id):
        return {"status": "error", "detail": "Invalid identifiers."}
    base = Path("output") / job_id / page_id
    teardown = base / "teardown.md"
    message = base / "message.txt"
    if not teardown.exists():
        return {"status": "error", "detail": "Report not found for this scan."}
    return {
        "status": "ok",
        "teardown": teardown.read_text(encoding="utf-8"),
        "message": message.read_text(encoding="utf-8") if message.exists() else "",
    }

@router.post("/outreach/send")
async def send_outreach(request: dict) -> dict:
    from ...outreach.dispatcher import send_outreach_email
    result = await send_outreach_email(
        to_email=request.get("email", "prospect@example.com"),
        subject=request.get("subject", "Ad Audit"),
        message_text=request.get("message_text", "")
    )
    return result
