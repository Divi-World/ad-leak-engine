"""Ephemeral swarm scrape runner [SEED: 2399].
Executes on a GitHub Actions runner (fresh IP, fresh browser).
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from ad_leak_engine.ingest.hybrid_router import HybridRouter

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--country", default="US")
    parser.add_argument("--max-results", type=int, default=50)
    parser.add_argument("--output-dir", default="output/swarm")
    parser.add_argument("--shard", type=int, default=None, help="Shard index for parallel execution")
    parser.add_argument("--total-shards", type=int, default=10, help="Total number of shards")
    args = parser.parse_args()

    source = HybridRouter()
    if args.shard is not None:
        source.playwright.shard_index = args.shard
        source.playwright.total_shards = args.total_shards
    ads = list(source.search(args.keyword, args.country, args.max_results))

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(datetime.now(timezone.utc).timestamp())
    out_file = out_dir / f"ads_{stamp}.json"
    out_file.write_text(
        json.dumps([ad.model_dump(mode="json") for ad in ads], indent=2, default=str),
        encoding="utf-8",
    )
    print(f"[SEED:2399] Collected {len(ads)} ads for '{args.keyword}' -> {out_file}")

if __name__ == "__main__":
    main()
