# Review 6 — Level 1 Completion Assessment
**Date:** 2026-09-21
**Branch:** main
**Status:** Architecture essentially right; raw preservation still incomplete

---

## Verdict

The latest push is a substantial improvement, but **Level 1 is not complete yet**. The architecture is now close; the remaining gap is mostly **source completeness + true raw preservation + real replay**, not more framework.

**Stop all Layer 2 development until this is done.**

---

## Current State

```
architecture:       essentially right
source discovery:   good
normalization:      moving correctly
operational tape:   partially real
raw preservation:   still incomplete
historical backfill: incomplete
source coverage:    missing 3 very important feeds
```

---

## P0 — Must fix before Level 1

### 1. `_store_raw()` still does not mean "raw"

The runner stores parsed Python objects, not original bytes:

```python
_store_raw(conn, "fca_pdmr", "notifications", {"count": count})
_store_raw(conn, "fca_ansp", "short_positions", {"count": count})
```

These are metadata summaries, not raw artifacts.

**Fix:** Replace with `ArtifactStore.put_bytes(response.content, metadata)`.

Every HTTP/file collector must persist original bytes **before parsing**.

### 2. Replay test is synthetic, not real

Current test creates fake data, not real source artifacts.

**Fix:** Use real fixtures (Yahoo response, FCA XLSX, CH JSON, PDMR HTML). Replay production parser against raw fixture. Hash comparison.

### 3. Missing 3 critical bulk feeds

- `ch_company_snapshot_monthly` — 469 MB full UK company snapshot
- `ch_accounts_bulk` — XBRL accounts bulk files
- `fca_nsm` — official FCA National Storage Mechanism (post-November-2025 PIP schema)

These are the highest-value additions because they preserve data you don't yet know you'll need.

---

## P1 — Important for completeness

### 4. Manifest/source inventory overstates diversity

RNS, PDMR, TR-1 are all from Investegate. filing_events is derived from CH.

Think: SOURCE → DATASETS → TRANSFORMATIONS

```
Layer 1 raw source: companies_house_filings
Layer 1 normalized fact: filing
Layer 2 / normalization transform: filing → corporate_event
```

### 5. PSC URL looks wrong, multipart

Current: `psc-snapshot-{date_str}.json.zip`
Actual: `psc-snapshot-2026-09-20_1of32.zip` through `_32of32.zip`

Must archive ZIP pieces, not inflate 2GB+ JSON.

### 6. `run_all()` doesn't run all manifests

12 manifests exist but only 6 collectors run. Need a collector registry.

### 7. Health measures execution, not data validity

Need three levels: source health, ingest health, data health.

### 8. Backfill state missing from manifests

Need `history.mode: backfill | partial | forward_only`.

### 9. Bulk datasets should not filter to 25 companies

PSC, CH snapshots, FCA data — store everything, filter downstream.

---

## What Level 1 should look like

```
L1A — RAW SOURCE TAPE
  official bytes/files
  timestamp, SHA256, source URL
  HTTP metadata, provider timestamp

L1B — NORMALIZED FACTS
  company, security, person, filing
  announcement, insider transaction
  ownership notification, price
  short position, financial fact

L1C — ENTITY MAP
  company_number, LEI, ISIN, ticker
  person IDs, validity ranges

L1D — MATERIALIZED STATE
  company-day, security-day, ownership-day
```

No causal signals. No conviction scores. Those begin Level 2/3.

---

## Acceptance test

```
raw/ only
    ↓
build blank DB
    ↓
replay ALL available fixture source artifacts
    ↓
materialize
    ↓
normalized_hash_A

delete DB
    ↓
replay again
    ↓
normalized_hash_B

A == B
```

---

## Priority order

1. ArtifactStore — raw bytes before parsing
2. Real replay tests with production parsers
3. ch_company_snapshot_monthly
4. ch_accounts_bulk
5. fca_nsm
6. Fix PSC multipart URLs
7. Collector registry for run_all()
8. History/backfill state in manifests
9. Health = source + ingest + data
10. Store bulk data unfiltered
