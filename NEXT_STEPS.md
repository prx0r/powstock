# POWSTOCK — Next Steps (Prioritized)

## Current State (2026-09-21)

**31/31 tests passing. 12 source manifests. 6,281 lines.**

### What Works
- Universe: 25 securities with hard-coded CH numbers, ISINs, LEIs
- Collectors: Yahoo prices, FCA short interest, Companies House, FCA PDMR, RNS, PSC snapshot, filing events, takeover panel, ch_bulk_parsers
- Layer 1: 12 manifests, health checks, standardized source state
- Layer 2: Signal stubs (insider pressure, short squeeze, filing activity)
- Idempotent inserts with deterministic event IDs
- Append-only raw storage with SHA256 provenance
- Nullable daily state (NULL = unknown, not zero)

### What's Broken/Incomplete
- `price_daily: 0 rows` — Yahoo collector runs but doesn't persist to DB
- `ingest_run`/`raw_artifact` tables not in existing DB (need migration)
- RNS returns 0 universe results (Investegate doesn't filter by ticker)
- `financials.py` needs `stream-read-xbrl` (not installed)
- `powuk_integration.py` hardcodes `/root/powuk` path (dead code)
- No end-to-end collector test

---

## Priority 1: Make the tape actually work

**Why:** The whole point of Layer 1 is to preserve the market/corporate tape. If prices aren't stored and the DB doesn't have the new schema, nothing downstream works.

### 1.1 Fix price storage
- `run_prices()` calls `fetch_all_latest()` which returns one price per ticker
- But `INSERT OR REPLACE INTO price_daily` should work — need to check why 0 rows
- Likely: Yahoo Finance blocking the server or returning empty results
- **Fix:** Add fallback to Stooq when Yahoo fails. Test both live.

### 1.2 Database migration
- Existing DB has old schema (no `ingest_run`, `raw_artifact`, no `event_id` columns)
- `init_db()` uses `CREATE TABLE IF NOT EXISTS` — old tables persist with old schema
- **Fix:** Add migration script that ALTERs existing tables to add new columns

### 1.3 End-to-end collector test
- Currently no test actually calls a live API
- **Fix:** Add integration test that runs each collector against live APIs (with timeout/skip if network unavailable)

---

## Priority 2: Clean up dead code

**Why:** Dead code creates confusion about what's real. The review specifically called this out.

### 2.1 Remove dead files
- `powstock/collectors/powuk_integration.py` — depends on `/root/powuk`, not portable
- `powstock/collectors/financials.py` — needs `stream-read-xbrl`, not installed
- `powstock/transforms/anomalies.py` — no consumer, Layer 2 signals replaced it
- `powstock/transforms/conviction.py` — arbitrary weights, review said to quarantine

### 2.2 Clean up __init__.py
- Remove imports of dead modules from `collectors/__init__.py`
- Keep only working collectors

---

## Priority 3: Make RNS actually useful

**Why:** RNS is one of the strongest UK data sources but currently returns 0 universe results.

### 3.1 Use Investegate advanced search
- Current: `searchtype=3` (all companies), filter client-side
- Fix: Use `searchtype=1` (company search) with ticker parameter
- Or: Scrape the announcement archive which has proper filtering

### 3.2 Alternative: LSE RNS feed
- LSE has a direct RNS feed at `https://api.londonstockexchange.com/`
- More reliable than Investegate scraping
- Would need to check if it's free/public

---

## Priority 4: Wire daily state materialization

**Why:** Daily state is the bridge between Layer 1 and Layer 2. Without it, signals can't be computed per-day.

### 4.1 Build `scripts/build_daily_state.py`
- The Makefile references it but it doesn't exist
- Should read from fact tables and produce `pow_company_state_daily`
- Must be idempotent: same inputs → same daily state

### 4.2 Add temporal join logic
- Join price data + insider data + short interest + company profiles per ticker per day
- Handle missing data as NULL (already done in schema)

---

## Priority 5: Layer 2 signal quality

**Why:** Signals are what make the garden useful. Currently just stubs.

### 5.1 Implement proper signal computation
- Insider pressure: weight by role (CEO > non-exec), recency, cluster
- Short squeeze risk: combine short interest + price momentum + days-to-cover
- Filing intensity: weight by event type severity (from filing_events.py)

### 5.2 Add cross-source signals
- Insider + short interest alignment (both bearish = stronger signal)
- RNS + insider timing (did insider buy before results announcement?)

---

## What NOT to do next

- **Don't build a universal economic schema** — that's Palantir territory
- **Don't add L2 order book** — needs IBKR, not free, defer
- **Don't add more collectors** — 12 sources is enough for checkpoint 1
- **Don't add dashboards** — premature
- **Don't add fish/powuk dependencies** — Layer 1 must stay independent

---

## Checkpoint 1 Definition (from review1.md)

```
wipe everything except raw/
        ↓
replay
        ↓
same normalized hashes
same event counts
same daily states
```

**To reach checkpoint 1, we need:**
1. ✅ Raw preservation (SHA256, append-only)
2. ✅ Idempotent inserts (event IDs, UPSERTs)
3. ✅ Nullable missing data (NULL not zero)
4. ✅ Temporal fields (effective_at, published_at, observed_at)
5. ❌ DB migration (old schema → new schema)
6. ❌ Price data actually stored (price_daily has 0 rows)
7. ❌ Replay test passing (wipe + replay = same state)
8. ❌ Daily state materialization from fact tables

**Estimated effort:** ~2-3 hours of focused work to close the gap.
