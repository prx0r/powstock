# BUILD_NOTES.md — Session Log

> Every change, every fix, every decision. Reverse chronological.

---

## Session: 2026-09-23 — powstock Integration + Data Fixes

### What We Set Out To Do
Wire powstock into powops for monitoring. Get all collectors producing data. Make signals work.

### What We Actually Did

#### 1. powops Integration (07:00-07:30)

**Problem:** powops couldn't see powstock data. Wrong path, wrong check type, wrong source IDs.

**Fixes:**
- `powops/sources.yaml`: Changed path from `/home/ubuntu/powstock` to `/root/powstock`
- Switched all powstock sources from `raw_mtime` to `collector_db` checks (raw dirs are empty — content is in objects/)
- Added `collector_run` VIEW to powstock DB that maps `ingest_run` to powops' expected schema
- Added heartbeat file writing to `run_all()` — writes `data/heartbeat.json` after each run
- Removed `api_key_env` checks from sources.yaml — powops monitors data flow, not key config

**Result:** 8/18 powstock sources showing green in powops.

#### 2. Price Backfill (07:45-08:00)

**Problem:** `price_daily` had 24 rows (1 day only). Momentum signals needed 200+ days.

**Fix:** Ran `scripts/backfill_prices.py --days 730` for all 25 universe tickers.

**Result:** 11,506 rows across 24/25 tickers (RHL missing — too new for Yahoo Finance). This single fix enabled 4 momentum signals.

#### 3. Insider Parser Fix (08:00-08:15)

**Problem:** Investegate PDMR collector returned global feed data. All 4 deals were for GTE (Gran Tierra), not our 25 universe tickers.

**Fix:** Added universe ticker filter to `run_insiders()`:
```python
universe_tickers = {s.ticker for s in UNIVERSE}
if deal["ticker"] not in universe_tickers:
    skipped += 1
    continue
```

**Result:** 25 non-universe deals correctly skipped. Zero universe deals found in current Investegate window (expected — our tickers rarely appear on the front page). Tracefour API still needed for ticker-specific queries.

#### 4. Short Interest Matching (08:15-08:30)

**Problem:** Only 2/25 tickers matched. Exact string matching failed because FCA data has "DRAX GROUP PLC" while universe has "DRAX".

**Fix:** Added `_normalize_company_name()` function that strips "PLC", "LIMITED", "GROUP", etc. Added partial matching (universe name contained in FCA name).

**Result:** 15/25 tickers matched (up from 2). 843 short interest positions total, 15 matched to universe.

#### 5. Artifact Variable Bugs (07:30-07:45)

**Problem:** 3 `run_*` functions referenced `artifact` variable before assignment when `artifact_store` was None or empty.

**Fix:** Added `artifact = None` initialization before the conditional block in `run_prices()`, `run_short_interest()`, and `run_rns()`.

**Result:** No more `UnboundLocalError` crashes.

#### 6. Filing Events Collector (08:30)

**Problem:** `run_filing_events()` was wired into `run_all()` but never produced `ingest_run` entries.

**Discovery:** Actually working — just hadn't been run recently. Produced 100 events on this run.

**Result:** Filing events now confirmed working.

#### 7. CH Bulk Collectors (08:30-08:45)

**Problem:** `ch_company_snapshot`, `ch_accounts_bulk`, `psc_snapshot` all failed because they tried to download today's data which doesn't exist yet.

**Fix:**
- `ch_company_snapshot.py`: Added fallback to previous month if current month not found
- `ch_accounts_bulk.py`: Added retry loop (last 7 days) with multiple filename patterns

**Result:** Collectors now gracefully handle missing data instead of crashing.

#### 8. Systemd Timer (08:45-09:00)

**Problem:** `run_all()` only ran when someone manually executed it.

**Fix:** Created `powstock-collect.service` + `powstock-collect.timer` — runs every 4 hours.

**Result:** Automated collection. Data refreshes without human intervention.

#### 9. Signal Testing (09:00-09:15)

**Problem:** No idea which signals actually worked.

**Test:** Ran all 11 signals against NG. (National Grid) and all 25 tickers.

**Results for NG.:**
| Signal | Status | Value |
|--------|--------|-------|
| insider_pressure | ✗ | None (no insider data) |
| short_interest_level | ✓ | 0.0145 |
| short_squeeze_risk | ✓ | 0.0145 |
| filing_event_signal | ✓ | 1.0 |
| alignment_score | ✓ | 0.9855 |
| anomaly_score | ✗ | None (needs insider data) |
| composite_score | ✓ | 0.7295 |
| price_momentum_50d | ✓ | 0.4203 (-7.97%) |
| price_momentum_200d | ✓ | 0.5132 (+1.32%) |
| moving_average_crossover | ✓ | 0.3959 (death cross) |
| drawdown_from_peak | ✓ | 0.6421 (-17.89%) |

**Universe coverage:**
- 23/25 tickers have momentum signals
- 14/25 tickers have short interest data
- 25/25 tickers have composite scores

#### 10. powops Final Status

```
  ✓ yahoo_finance                     24
  ✓ investegate_rns                  891
  ✓ companies_house                   25
  ✓ investegate_pdmr                  20
  ✓ fca_ansp                         422
  ✓ takeover_panel                     1
  ✓ fca_tr1                           30
  ✓ commodity_prices                   5
  ○ 10 blocked (external services)
```

---

## Key Decisions

1. **collector_db over raw_mtime** — powstock stores content in global objects/, not per-source dirs. collector_db checks the ingest_run table directly, which is more reliable.

2. **Filter insiders to universe only** — The Investegate global feed returns deals for any company. We only care about our 25 tickers. Non-universe deals are skipped.

3. **Fuzzy name matching for short interest** — Exact string matching failed. Normalizing company names (stripping PLC, LIMITED, GROUP) improved matches from 2 to 15.

4. **Remove api_key_env from powops** — powops should monitor data flow, not key configuration. The key check happens in the collector code, not in powops.

5. **Systemd timer over cron** — systemd provides better logging, dependency management, and persistence.

6. **Cancel DMO/FCA NSM fixes** — Both are behind anti-bot protection (ShieldSquare/Cloudflare). Would need proxy or browser-based scraping. Low impact — other collectors provide similar data.

---

## What Changed (Files)

### powstock
- `powstock/collectors/runner.py` — Fixed artifact bugs, added universe filtering, added `_normalize_company_name()`, added heartbeat writing, added collector_run view
- `powstock/collectors/fca_pdmr.py` — Filter numeric-only director names
- `powstock/collectors/ch_company_snapshot.py` — Fallback to previous month
- `powstock/collectors/ch_accounts_bulk.py` — Retry last 7 days
- `scripts/backfill_prices.py` — Used for 2-year backfill
- `BLOCKERS.md` — New file documenting external service blockers
- `POWOPS_INTEGRATION.md` — New file for powops integration reference
- `.gitignore` — Added DB WAL/SHM files, heartbeat.json

### powops
- `powops/sources.yaml` — Fixed path, switched to collector_db, added 18 powstock sources, removed api_key_env checks

---

## Quantitative Results

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| price_daily rows | 24 | 11,506 | +11,482 |
| Universe tickers with prices | 1 | 24 | +23 |
| Short interest matched | 2 | 15 | +13 |
| Signals producing output | 2 | 9 | +7 |
| powops active sources | 7 | 8 | +1 |
| Collectors in run_all() | 18 | 18 | 0 |
| Collectors producing data | 8 | 11 | +3 |
| Automated collection | No | Yes (4h timer) | New |

---

## Remaining Blockers

See `BLOCKERS.md` for full list. Summary:
- **Tracefour API key** — Needed for universe insider data (highest priority)
- **DMO Gilts** — Behind ShieldSquare (needs proxy)
- **FCA NSM** — Behind Cloudflare (needs proxy)
- **UK Parliament** — Timeout (needs retry logic)
- **European Insiders** — Timeout (needs retry logic)
- **Congress Trades** — 403 + parse errors (needs parser update)
- **CH Bulk Downloads** — Timing (fixed with fallback logic, but large files may timeout)
