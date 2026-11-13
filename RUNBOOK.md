# Ad-Leak-Engine Runbook [SEED: 2399]

## Master Commands
- `./scripts/ale scan <keyword> <country> [--limit N] [--skip-crawl]` : Full pipeline execution
- `./scripts/ale feedback <page_id> "<reply_text>"` : Self-improvement feedback loop
- `./scripts/ale test` : Run the full test suite

## Troubleshooting
- **No ads extracted:** Meta's schema may have drifted. The system relies on regex fallback. Inspect `data/debug/`.
- **L2/L3 Crawl Skipped:** Prospect's landing page has aggressive bot protection. The system safely skips to prevent IP bans.
- **Platform = custom (0.30):** The fingerprinter couldn't confidently identify Shopify/WooCommerce/BigCommerce. The system safely defaults to generic GTM/Server-side fixes.

## Log Inspection
All structured logs are written to `logs/engine.log` in JSON format for easy parsing:
`cat logs/engine.log | grep "ERROR"`
## Recovery: `fatal: bad object HEAD`

Symptom: `git status` / `git log` fails with `fatal: bad object HEAD`,
and `git fsck --full` reports many `missing blob` / `invalid sha1` errors.

Diagnosis:
- Check `.git/objects/pack/` exists and contains `.pack` + `.idx` files.
  If missing, the packed object store was lost (interrupted gc, folder copy, etc.).
- `git cat-file -t <sha-in-reflog>` will confirm whether a given commit object
  exists locally.

Recovery (safe, no data loss):
1. Back up the working tree first: `cp -r <repo> <repo>.backup-$(date +%Y%m%d-%H%M)`
2. `git fetch --all --prune --force` - pulls missing objects from the remote.
3. `git cat-file -t <bad-sha>` should now print `commit`.
4. `git fsck --full` should be clean (dangling blobs OK).
5. `git status` works again.

If HEAD/config/index are missing (e.g., accidentally deleted):
- They are also in the backup from step 1. Restore with:
  cp -p <backup>/.git/HEAD   .git/HEAD
  cp -p <backup>/.git/config .git/config
  cp -p <backup>/.git/index  .git/index

Never:
- `git gc` / `git prune` on a repo with a broken object store (can commit the damage).
- Manually `echo` into `.git/refs/*` - use `git update-ref`.
- `find ... -exec rm` in a repo you care about.
