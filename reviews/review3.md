# Review 3 — Layer 1 Final Completion Pass

**Date:** 2026-09-21
**Reviewer:** opencode (automated)
**Status:** Pre-completion audit

---

## Verdict

The architecture is right. The remaining work is refinement and removing the last places where the implementation still claims stronger guarantees than it actually provides.

---

## Final Issues to Fix

### 1. ArtifactStore not globally content-addressed
Current layout `data/raw/{source}/{today}/{sha_prefix}_{dataset}.bin` allows duplicate storage of identical bytes on different days. Fix: `data/raw/objects/{ab}/{cd}/{sha256}.bin` + `data/raw/receipts/{source}/{date}/{run}.json`.

### 2. raw_artifact.run_id = 0 is structurally wrong
Every collection attempt should have real ingest_run lifecycle: start → fetch → store → parse → complete.

### 3. Enable SQLite foreign keys
`PRAGMA foreign_keys = ON` immediately after connect.

### 4. Prices don't preserve original provider response
`run_prices()` stores reconstructed JSON, not raw Yahoo HTTP response bytes. Fix: expose `fetch_raw()` + `parse_raw()` per collector.

### 5. run_all() doesn't use the registry
Hardcoded collection sequence instead of manifest-driven execution.

### 6. filing_events is not a Layer 1 source
It's derived from Companies House filing history. Normalize naming.

### 7. RNS/PDMR/TR-1 should be organized around FCA NSM
NSM is canonical. Investegate is mirror/fallback.

### 8. FCA NSM 403 should be AUTH_REQUIRED not OK
Health statuses need explicit states.

### 9. Separate source health from collection health
Compute: reachable, authenticated, artifact_expected, artifact_observed, etc.

### 10. Historical collection status needs to become executable
Build backfill scripts per source.

### 11. Actually backfill what is available now
Price history, CH accounts, company snapshots, regulatory announcements.

### 12. PSC daily archive should store a daily manifest
`snapshot_manifest.json` per date.

### 13. CH accounts should be archive-first
Don't build universal XBRL engine yet. Archive raw ZIPs.

### 14. CH full company snapshots should not filter at ingestion
Store everything, filter downstream.

### 15. Fix ArtifactStore.list_artifacts()
Use DB as canonical index, not filesystem traversal.

### 16. Metadata files should not be authoritative ledger
DB is canonical. Sidecar .meta.json is disaster recovery mirror.

### 17. Add R2 mirroring
Local-first, then replicate to R2 with verification.

### 18. Don't make daily.py the Level 1 daemon
Split into layer1_collect.py, layer1_backfill.py, layer1_verify.py.

### 19. powk should not be hard dependency of Layer 1
Layer 1 deps: httpx, pydantic, pyyaml. Layer 2: powk, numpy, etc.

### 20. Artifact lineage on every fact
Every normalized fact: source_id, artifact_id, parser_name, parser_version, observed_at.

### 21. Parser version must change with code
Compute from git commit, not hardcoded string.

### 22. Keep unknowns explicit everywhere
NULL != 0. parse_status, confidence, group_value patterns.

### 23. Remove PROPOSAL.md Layer 2 tasks from scope
Tracefour relevant only as raw source, not cluster signals.

### 24. Define canonical Level 1 directory structure
sources/ parsers/ schema/ separation.

### 25. Final tests should be harder
Byte preservation, global dedupe, FK integrity, offline replay, whole-garden rebuild.

---

## Completion Definition

POWStock Layer 1 is finished when:

1. Every enabled source archives original bytes before parsing.
2. Every normalized fact points back to exact artifact bytes and parser version.
3. Every source has explicit historical coverage and continuity state.
4. The complete normalized database can be rebuilt offline from retained raw artifacts.
5. A second rebuild produces byte/logically identical canonical facts.
6. Collection runs independently of POWK, signals, fish, or any Layer 2/3 system.
