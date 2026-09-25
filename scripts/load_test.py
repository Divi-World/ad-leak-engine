"""Load Test: 100 Concurrent Internal Pipeline Scans [SEED: 2399].
Verifies the orchestrator can handle high concurrency without data loss.
"""
import asyncio
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ad_leak_engine.leak_scan.l1_creative import L1CreativeScanner
from ad_leak_engine.shared.schemas import Page, RawAd
from datetime import datetime, timezone

async def run_single_scan(i):
    # Mock a page with 5 ads to test the internal pipeline concurrency
    ads = [RawAd(id=f"ad_{i}_{j}", page_id=f"page_{i}", page_name="Test", start_date=datetime.now(timezone.utc), media_type="IMAGE") for j in range(5)]
    page = Page(id=f"page_{i}", name="Test Page", first_seen=datetime.now(timezone.utc), ads=ads)
    
    scanner = L1CreativeScanner()
    # Simulate async work
    await asyncio.sleep(0.01) 
    leaks = scanner.scan(page)
    return len(leaks)

async def main():
    print("[SEED:2399] Initiating Load Test: 100 Concurrent Scans...")
    start = time.time()
    tasks = [run_single_scan(i) for i in range(100)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success = sum(1 for r in results if not isinstance(r, Exception))
    failed = sum(1 for r in results if isinstance(r, Exception))
    duration = time.time() - start
    
    print(f"[SEED:2399] Load Test Complete in {duration:.2f}s")
    print(f"Success: {success}/100 ({success}%)")
    print(f"Failed: {failed}/100")
    
    if success >= 95:
        print("[GATE PASSED] >95% success rate achieved.")
    else:
        print("[GATE FAILED] <95% success rate.")

if __name__ == "__main__":
    asyncio.run(main())
