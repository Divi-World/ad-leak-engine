"""Aggregate swarm results from GitHub Actions artifacts into SQLite [SEED: 2399]."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from ad_leak_engine.shared.schemas import RawAd
from ad_leak_engine.persistence.db import init_db
from ad_leak_engine.persistence.repository import AdRepository

def download_artifacts(run_id: str = None):
    swarm_dir = Path("output/swarm")
    swarm_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["gh", "run", "download", "--dir", str(swarm_dir), "--pattern", "swarm-shard-*"]
    if run_id: cmd.extend(["--run", run_id])
    print(f"[SEED:2399] Downloading artifacts via: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"[SEED:2399] Artifact download failed: {e}")

def aggregate():
    swarm_dir = Path("output/swarm")
    if not swarm_dir.exists():
        print("[SEED:2399] No output/swarm directory found.")
        return

    all_ads = []
    seen = set()
    json_files = list(swarm_dir.glob("*.json")) + list(swarm_dir.glob("*/*.json"))
    
    for f in sorted(json_files):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(data, list): continue
            for item in data:
                for key in ("impressions", "spend"):
                    if isinstance(item.get(key), list): item[key] = tuple(item[key])
                ad = RawAd(**item)
                if ad.id not in seen:
                    seen.add(ad.id)
                    all_ads.append(ad)
        except Exception as e:
            print(f"[SEED:2399] Skipping {f.name}: {e}")

    init_db()
    repo = AdRepository()
    inserted = repo.upsert_ads(all_ads)
    print(f"[SEED:2399] Aggregated {len(all_ads)} unique ads from {len(json_files)} files.")
    print(f"[SEED:2399] Inserted {inserted} NEW ads into SQLite database.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--run-id", type=str)
    args = parser.parse_args()
    if args.download: download_artifacts(args.run_id)
    aggregate()
