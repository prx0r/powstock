# Review 1 — powstock Deep Dive
**Date:** 2026-09-21
**Branch:** main
**Reviewer:** opencode (automated)

---

## Verdict

The direction is strong, but checkpoint 1 is not complete yet. The repo currently gives an impression of being further along than the underlying data guarantees actually are. The next work should be almost entirely boring ingestion/integrity work—not more signals.

---

## Architecture Gap

The architecture says:

```
source
→ immutable raw
→ normalized
→ entity resolution
→ daily state
→ transformations
→ experiments
```

But the implementation is currently closer to:

```
source
→ scrape/parse immediately
→ partial SQLite row
→ sometimes save summary
→ derive signal
```

**Invariant to enforce before anything else:**

> Every normalized datum must be reproducible from an immutable, timestamped source artifact stored by POWStock.

---

## P0 — fix these immediately

### 1. Companies House API key is committed

Hardcoded in:
- `powstock/collectors/companies_house.py`
- `powstock/entities/resolver.py`

Remove, rotate key, use settings/env only. Entity resolver should not know auth exists.

### 2. Raw preservation is false in several collectors

Runner does `_store_raw(conn, "fca_pdmr", "notifications", {"count": count})` — source is thrown away.

Raw garden should contain actual source artifacts (HTML, XLSX, etc.), not summaries.

### 3. RNS pagination broken

`fetch_investegate_page()` doesn't put `page` into request parameters. Pages 1-N all fetch page 1. PDMR has same problem.

### 4. PDMR parser invents data

```python
shares_per_director = total_shares // len(director_pairs)
```

If source says "Alice + Bob = 100,000 shares" and individual allocation unknown, store:

```python
shares = NULL
group_shares = 100000
parse_status = PARTIAL
```

Do NOT fabricate precision.

### 5. Missing data represented as zero

`PowCompanyStateDaily` initializes everything with `0.0`, `0`, `""`. "No data" becomes "zero employees". Use nullable values.

---

## P0.5 — Runtime defect

`Filing` dataclass has no `raw` field but `fetch_company_filings()` passes `raw=item`. This will raise TypeError.

---

## P1 — Key issues

### PSC collector
- Provenance bug on fallback dates (stores under wrong date)
- Inflates entire UK snapshot into one Python list
- `fetch_universe_psc()` conflates bulk snapshot with API current data

### Runner needs ingestion ledger
- Currently doing schema creation, collection, normalization, storage, observations, status, orchestration — all in one
- Needs `ingest_run` + `raw_artifact` tables for proper receipt chain

### Bug in `_store_raw`
- Stores `len(raw_bytes)` as row count when `data` is a list. Should be `len(data)`.

### Normalized tables need natural/event keys
- Missing UNIQUE constraints → duplicates on repeated runs
- Need idempotent UPSERTs

### Stop swallowing exceptions
- `except Exception: return []` hides source failures
- Need explicit states: OK, EMPTY_VALID, PARTIAL, SOURCE_ERROR, PARSE_ERROR, SCHEMA_DRIFT, RATE_LIMITED

### Entity resolution too optimistic
- "Search CH by name, take first result" is guessing
- Build persistent `security_entity_map` with manual verification for 25 seed names
- Person resolution needs CH officer ID priority, not just sha256(name)

### Conviction score is research theatre
- Arbitrary weights (CEO +0.25, £1m +0.3, streak +0.2, drawdown +0.15)
- Keep primitives, test transformations later, version them

### Daily state shouldn't be truth table
- Should be materialized view rebuilt from fact tables
- Fact tables should preserve event/fact structure for replay

### Temporal semantics missing
- Need effective_at, published_at, observed_at everywhere
- Otherwise look-ahead bias in backtests

---

## P2 — Important but later

- RNS/PDMR strategy: archive originals, not AI summaries
- TR-1: currently headline filter, needs proper field parsing
- Takeover Panel: archive first, parse later
- Universe should support discovered entities beyond seed 25
- "Thinner markets are better sensors" should be experiment H001, not architecture
- Documentation drifting — need `powstock doctor` for auto-status

---

## Priority Fix Order

1. Rotate/remove CH secret
2. Build generic immutable ArtifactStore
3. Build ingest_run + raw_artifact ledger
4. Make every collector save response bytes before parsing
5. Add SHA256/content-addressed dedupe
6. Add explicit temporal fields
7. Add unique event IDs and idempotent UPSERTs
8. Fix Investegate pagination
9. Remove PDMR invented share splitting
10. Fix PSC snapshot date provenance + stream instead of load-all
11. Fix Filing(raw=...) runtime bug
12. Make missing data nullable
13. Add fixture corpus + replay/idempotence tests
14. Hard-code 25 company-number/LEI/ISIN mappings
15. Wire daily-state materialization last

---

## Checkpoint 1 Definition

```
                 SOURCE
                   │
                   ▼
             raw bytes/files
                   │
          SHA256 + timestamps
                   │
                   ▼
             RAW ARTIFACT
                   │
             parser vN
                   ▼
          NORMALIZED EVENT
                   │
          canonical entity IDs
                   ▼
              FACT TABLES
                   │
        deterministic materialize
                   ▼
          COMPANY DAILY STATE
```

**Passing test:**
```
wipe everything except raw/
        ↓
replay
        ↓
same normalized hashes
same event counts
same daily states
```
