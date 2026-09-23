# THREADS.md — Open Threads

> Everything that's in progress, blocked, or planned. A new agent reads this to know what's happening.

---

## Active Threads

### T1: Price History Backfill — DONE
- **Status:** Complete
- **What:** 11,506 rows across 24/25 tickers (2 years daily OHLCV)
- **Impact:** Enabled 4 momentum signals (50d, 200d, MA crossover, drawdown)
- **Done:** 2026-09-23

### T2: Insider Data for Universe — BLOCKED
- **Status:** Blocked on Tracefour API key
- **What:** Investegate global feed rarely includes our 25 tickers. Need ticker-specific queries.
- **Impact:** Without this, insider_pressure and anomaly_score signals return None. 4 of 10 signals dead.
- **Blocker:** Need human to register at https://www.tracefour.com and set `POWSTOCK_TRACEFOUR_API_KEY` in .env
- **Priority:** CRITICAL — single highest-impact unblock

### T3: Short Interest Matching — DONE
- **Status:** Complete
- **What:** 15/25 tickers matched (ISIN + normalized name matching)
- **Impact:** short_interest_level and short_squeeze_risk signals now work for 15 tickers
- **Done:** 2026-09-23

### T4: powops Integration — DONE
- **Status:** Complete
- **What:** 8/18 powstock sources showing green in powops
- **Impact:** Can monitor data flow from dashboard
- **Done:** 2026-09-23

### T5: Automated Collection — DONE
- **Status:** Complete
- **What:** systemd timer runs every 4 hours
- **Impact:** Data refreshes without human intervention
- **Done:** 2026-09-23

### T6: CH Bulk Collectors — PARTIALLY FIXED
- **Status:** Timing fixed, but large files may timeout
- **What:** `ch_company_snapshot` and `ch_accounts_bulk` now try previous dates if current not available
- **Impact:** These are historical data, not real-time. Low priority.
- **Remaining:** Files are ~469MB. May need increased timeout or background download.

### T7: FCA NSM — BLOCKED
- **Status:** Blocked on Cloudflare
- **What:** FCA National Storage Mechanism returns 403 (ShieldSquare/Cloudflare)
- **Impact:** Low — filing_events collector already gets this data from Companies House
- **Blocker:** Need proxy, cookies, or browser-based scraping

### T8: DMO Gilts — BLOCKED
- **Status:** Blocked on ShieldSquare
- **What:** DMO gilt yield curve returns HTML captcha instead of CSV
- **Impact:** Low — supplementary macro data, not critical for signals
- **Blocker:** Need proxy or manual data

### T9: UK Parliament Collector — BLOCKED
- **Status:** Timeout on HTTP requests
- **What:** MP shareholdings register hangs
- **Impact:** Low — nice-to-have, not critical for signals
- **Blocker:** Need increased timeout, retry logic, or rate limit handling

### T10: European Insiders — BLOCKED
- **Status:** Timeout on HTTP requests
- **What:** BaFin/AMF/AFM insider trading notifications hang
- **Impact:** Low — supplementary data
- **Blocker:** Need increased timeout or rate limit handling

### T11: Congress Trades — BLOCKED
- **Status:** Parse errors + 403
- **What:** House XML malformed, Senate CSRF token + 403
- **Impact:** Low — US data, not UK-focused
- **Blocker:** Need parser update for new HTML structure

### T12: Entity Resolver — DEAD
- **Status:** Code exists but never wired into pipeline
- **What:** Would link directors across companies (who sits on multiple boards)
- **Impact:** Medium — enables cross-company insider analysis
- **Blocker:** Needs wiring into daily pipeline + testing with real data
- **Note:** Import bug already fixed (httpx was imported)

### T13: Financial Fundamentals (XBRL) — NOT STARTED
- **Status:** `financials.py` exists but missing `stream-read-xbrl` dependency
- **What:** Would extract revenue, cash, debt, employees from Companies House iXBRL accounts
- **Impact:** Medium — daily state table currently has mostly NULL financial fields
- **Blocker:** Need to install `stream-read-xbrl` and implement parser

### T14: Collector Registry Refactoring — NOT STARTED
- **Status:** 20 collectors registered in layer1/registry.py but run_all() has hardcoded calls
- **What:** Refactor run_all() to derive from registry instead of hardcoded try/except blocks
- **Impact:** Low — functional as-is, just not DRY
- **Blocker:** None, just not prioritized

### T15: Signal Validation — IN PROGRESS
- **Status:** 9/11 signals tested and working
- **What:** Need to validate signals produce meaningful output across all 25 tickers
- **Impact:** High — proves the analysis layer works
- **Progress:** 23/25 tickers have momentum signals, 14/25 have short interest, 25/25 have composite scores

### T16: Experiments — NOT STARTED
- **Status:** `layer2/experiments/` directory is empty
- **What:** Need to run first seesaw experiment (constraint pressure vs financial repricing)
- **Impact:** Critical for thesis validation
- **Blocker:** Needs T2 (insider data) and T15 (signal validation) complete first

---

## Resolved Threads

### T-R1: Artifact Variable Bugs — RESOLVED
- **What:** 3 run_* functions referenced `artifact` before assignment
- **Fix:** Added `artifact = None` initialization
- **Date:** 2026-09-23

### T-R2: Insider Parser Non-Universe Data — RESOLVED
- **What:** Investegate PDMR collector returned global feed, not universe tickers
- **Fix:** Added universe ticker filter to run_insiders()
- **Date:** 2026-09-23

### T-R3: Filing Events Not Producing Data — RESOLVED
- **What:** run_filing_events() never produced ingest_run entries
- **Fix:** Actually working — just hadn't been run recently
- **Date:** 2026-09-23

### T-R4: powops Path Wrong — RESOLVED
- **What:** powops sources.yaml pointed to /home/ubuntu/powstock
- **Fix:** Changed to /root/powstock
- **Date:** 2026-09-23

---

## Future Threads (Not Started)

### F1: UK Robotics Parts Intelligence
- **What:** Canonical product identity, compatibility, pricing from powproducts garden
- **Impact:** Commercial product
- **Dependencies:** powproducts collectors need implementation

### F2: Supply Chain Intelligence
- **What:** HMRC trade flows, UKRI grants, component pricing from powrobots garden
- **Impact:** Commercial product
- **Dependencies:** powrobots collectors need implementation + API keys

### F3: Repair Outcomes Data
- **What:** Package repair data as API for repair businesses, insurers, manufacturers
- **Impact:** Revenue
- **Dependencies:** repair garden already has data

### F4: powuk Constraint Collectors
- **What:** NESO demand/generation, PV Live, planning apps from powuk garden
- **Impact:** Seesaw thesis requires constraint data
- **Dependencies:** powuk collectors need implementation (APIs are free)

---

## Thread Priority Map

```
CRITICAL: T2 (Tracefour) → unlocks T16 (experiments)
HIGH:     T15 (signal validation) → T16 (experiments)
MEDIUM:   T13 (XBRL), T12 (entity resolver), T6 (CH bulk)
LOW:      T14 (registry refactor), T7-T11 (blocked collectors)
FUTURE:   F1-F4 (commercial products)
```
