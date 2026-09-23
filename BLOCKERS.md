# BLOCKERS.md — What I Can't Do

> Things that need human intervention. Everything else is done.

---

## API Keys Needed

### Tracefour API Key (HIGHEST PRIORITY)
- **What:** Structured UK PDMR insider dealing data, queryable by ticker
- **Why:** Without this, insider deals for our 25 universe tickers depend on Investegate global feed (which rarely includes our tickers)
- **Unblocks:** insider_pressure, anomaly_score signals; powstock-insiders MCP tool returns universe data
- **Cost:** Free (60 req/hr)
- **Where:** https://www.tracefour.com
- **Env var:** `POWSTOCK_TRACEFOUR_API_KEY`
- **Status:** NOT REGISTERED — needs human to sign up

### Finnhub API Key
- **What:** Backup insider transaction data (SEC filings for UK tickers)
- **Why:** Fallback if Tracefour is down
- **Unblocks:** Backup insider source
- **Cost:** Free (60 calls/min)
- **Where:** https://finnhub.io
- **Env var:** `POWSTOCK_FINNHUB_API_KEY`
- **Status:** NOT REGISTERED — needs human to sign up

---

## External Service Blockers

### FCA NSM — Cloudflare 403
- **What:** FCA National Storage Mechanism filings
- **Error:** `403 Forbidden` from `data.fca.org.uk/api/nsm`
- **Cause:** FCA website blocks automated requests with ShieldSquare/Cloudflare
- **Fix:** Need proxy, cookies, or browser-based scraping
- **Impact:** Low — filing_events collector already gets this data from Companies House
- **Status:** BLOCKED — needs proxy solution

### DMO Gilts — ShieldSquare
- **What:** UK gilt yields and BoE rates
- **Error:** Returns HTML captcha instead of CSV
- **Cause:** DMO website behind ShieldSquare anti-bot
- **Fix:** Need proxy or manual data
- **Impact:** Low — supplementary macro data, not critical for signals
- **Status:** BLOCKED — needs proxy solution

### UK Parliament — Timeout
- **What:** MP shareholdings register
- **Error:** Hangs on HTTP requests (no output after 30s)
- **Cause:** Parliament website is slow or rate-limiting
- **Fix:** Increase timeout to 60s, add retry with backoff
- **Impact:** Low — nice-to-have, not critical for signals
- **Status:** TIMEOUT — needs retry logic

### European Insiders — Timeout
- **What:** BaFin/AMF/AFM insider trading notifications
- **Error:** Hangs on HTTP requests
- **Cause:** European regulator websites are slow or blocking
- **Fix:** Increase timeout to 60s, add retry
- **Impact:** Low — supplementary data
- **Status:** TIMEOUT — needs retry logic

### Congress Trades — 403 + Parse Error
- **What:** US Congress trading disclosures
- **Errors:**
  - House: `XML parse error: not well-formed`
  - Senate: `CSRF token not found` + `403 Forbidden`
- **Cause:** Congress websites changed structure or block scrapers
- **Fix:** Update parsers for new HTML structure
- **Impact:** Low — US data, not UK-focused
- **Status:** BROKEN — needs parser update

---

## Code Issues (Can Fix, Not Yet Done)

### Entity Resolver — Revivable
- **Status:** Code exists at `powstock/entities/resolver.py`, marked DEAD but import bug fixed
- **What it does:** Links directors across companies (who sits on multiple boards)
- **What's needed:** Wire into daily pipeline, test with real data
- **Priority:** Medium — enables cross-company insider analysis
- **Status:** NOT WIRED — needs testing

### Financial Fundamentals (XBRL) — Missing Dependency
- **Status:** `powstock/collectors/financials.py` exists but missing `stream-read-xbrl`
- **What it would do:** Extract revenue, cash, debt, employees from Companies House iXBRL accounts
- **What's needed:** `pip install stream-read-xbrl`, test parser
- **Priority:** Medium — daily state table currently has mostly NULL financial fields
- **Status:** NOT STARTED — needs dependency install

### Collector Registry — Not Used for Execution
- **Status:** 20 collectors registered in `layer1/registry.py` but `run_all()` has hardcoded calls
- **What's needed:** Refactor `run_all()` to derive from registry
- **Priority:** Low — functional as-is, just not DRY
- **Status:** NOT STARTED — not prioritized

---

## What's Done (For Reference)

### Data Collection
- [x] Price backfill: 11,506 rows across 24/25 tickers (2 years)
- [x] Insider parser: filters to universe tickers only
- [x] Short interest matching: 15/25 tickers matched (ISIN + name)
- [x] 3 artifact bugs fixed (uninitialized variable)
- [x] Filing events collector: now working (100 events)
- [x] CH bulk collectors: timing fallback (previous month/7 days)
- [x] Systemd timer: automated collection every 4 hours

### Infrastructure
- [x] powops integration: 8/18 sources active, collector_db checks
- [x] API server: FastAPI with 15+ endpoints (port 8797)
- [x] MCP server: 11 tools for powops and agents
- [x] Heartbeat file: written after each run_all()
- [x] collector_run view: maps ingest_run to powops schema

### Documentation
- [x] DEVPLAN: rewritten with honest assessment
- [x] DEVPLANRESPONSE: full repo audit
- [x] BUILD_NOTES: session log of all changes
- [x] THREADS: 16 open threads, 4 resolved, 4 future
- [x] POWOPS_INTEGRATION: how monitoring works
- [x] BLOCKERS: this file

---

## Summary

| Category | Count | Action Needed |
|----------|-------|---------------|
| API keys needed | 2 | Human to register |
| External services blocked | 5 | Proxy or manual work |
| Code issues | 3 | Can fix when prioritized |
| **Total blockers** | **10** | **2 need human, 5 need proxy, 3 need code work** |
