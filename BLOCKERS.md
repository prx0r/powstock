# BLOCKERS.md — What I Can't Do

> Things that need human intervention. Everything else is done.

---

## API Keys Needed

### Tracefour API Key (HIGHEST PRIORITY)
- **What:** Structured UK PDMR insider dealing data, queryable by ticker
- **Why:** Without this, insider deals for our 25 universe tickers depend on Investegate global feed (which rarely includes our tickers)
- **Unblocks:** insider_pressure, alignment_score, anomaly_score, composite_score signals
- **Cost:** Free (60 req/hr)
- **Where:** https://www.tracefour.com
- **Env var:** `POWSTOCK_TRACEFOUR_API_KEY`

### Finnhub API Key
- **What:** Backup insider transaction data (SEC filings for UK tickers)
- **Why:** Fallback if Tracefour is down
- **Cost:** Free (60 calls/min)
- **Where:** https://finnhub.io
- **Env var:** `POWSTOCK_FINNHUB_API_KEY`

---

## External Service Blockers

### FCA NSM — Cloudflare 403
- **What:** FCA National Storage Mechanism filings
- **Error:** `Client error '403 Forbidden' for url 'https://data.fca.org.uk/api/nsm?page=1&pageSize=50'`
- **Cause:** FCA website blocks automated requests with Cloudflare
- **Fix:** Need proxy, cookies, or browser-based scraping
- **Impact:** Low (filing_events collector already gets this data from Companies House)

### UK Parliament — Timeout
- **What:** MP shareholdings register
- **Error:** Hangs on HTTP requests (no output after 30s)
- **Cause:** Parliament website is slow or rate-limiting
- **Fix:** Increase timeout, add retry with backoff
- **Impact:** Low (nice-to-have, not critical for signals)

### European Insiders — Timeout
- **What:** BaFin/AMF/AFM insider trading notifications
- **Error:** Hangs on HTTP requests
- **Cause:** European regulator websites are slow or blocking
- **Fix:** Increase timeout, add retry
- **Impact:** Low (supplementary data, not core)

### Congress Trades — 403 + Parse Error
- **What:** US Congress trading disclosures
- **Errors:**
  - House: `XML parse error: not well-formed`
  - Senate: `CSRF token not found` + `403 Forbidden`
- **Cause:** Congress websites changed structure or block scrapers
- **Fix:** Update parsers for new HTML structure
- **Impact:** Low (US data, not UK-focused)

### DMO Gilts — 404
- **What:** UK gilt yields and BoE rates
- **Error:** `404 Not Found for url 'https://www.dmo.gov.uk/resdata/opendata/gilt-repo/yld_CURVE.csv?csv=1'`
- **Cause:** DMO changed their data URL
- **Fix:** Find new URL, update collector
- **Impact:** Low (supplementary macro data)

### CH Bulk Downloads — Timing
- **What:** Companies House monthly snapshots (company data, accounts, PSC)
- **Error:** `CH snapshot not found for 2026-09` / `CH accounts bulk not found for 2026-09-22`
- **Cause:** Bulk data isn't published daily — monthly or quarterly
- **Fix:** Adjust collector to check for latest available month, not current date
- **Impact:** Medium (historical data, not real-time)

---

## Code Issues (Can Fix, Not Yet Done)

### Finnhub Collector — Not Tested
- **Status:** Wired into run_all(), never successfully run
- **Needs:** API key + test run
- **Priority:** Low (Tracefour is primary insider source)

### Entity Resolver — Dead Code
- **Status:** Import bug fixed, but never wired into pipeline
- **Needs:** Wire into daily pipeline, test with real data
- **Priority:** Medium (enables cross-company insider analysis)

### Collector Registry — Not Used
- **Status:** 20 collectors registered in layer1/registry.py, but run_all() has hardcoded calls
- **Needs:** Refactor run_all() to derive from registry
- **Priority:** Low (functional as-is, just not DRY)

---

## What's Done (For Reference)

- [x] Price backfill: 11,506 rows across 24/25 tickers
- [x] Insider parser: filters to universe tickers only
- [x] Short interest matching: 15/25 tickers matched (ISIN + name)
- [x] 3 artifact bugs fixed (uninitialized variable)
- [x] Filing events collector: now working (100 events)
- [x] Systemd timer: automated collection every 4 hours
- [x] powops integration: 8/18 sources active
- [x] BLOCKERS.md: this file
