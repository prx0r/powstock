# DevPlan — POW System

> Zoomed-out development plan for the entire POW ecosystem. Architecture is done. Data is not. This plan fixes that.

---

## Where We Are (Honest Assessment)

```
Architecture:   ████████████████████ 95% — layered design, content-addressed storage, monitoring
Infrastructure: ████████████████░░░░ 80% — ArtifactStore, IngestRun, powops dashboard, MCP
Data Collection:██████░░░░░░░░░░░░░░ 13/46 sources collecting (28%)
Data Quality:   ███░░░░░░░░░░░░░░░░░ 1 day prices, wrong-ticker insiders, no fundamentals
Analysis:       ██░░░░░░░░░░░░░░░░░░ 2/10 signals producing meaningful output
Experiments:    ░░░░░░░░░░░░░░░░░░░░ 0 — thesis untested
Commercial:     ░░░░░░░░░░░░░░░░░░░░ 0 — no products, no revenue
```

**The single biggest risk:** We keep building architecture while the data stays thin. Every week without historical prices and universe-matched insider data is a week the thesis can't be tested.

---

## What "Done" Looks Like

### Phase 0 — Data Flow (the tape exists)
- 25 universe tickers have 2+ years of daily price history
- Insider deals match our 25 tickers (not random stocks)
- Every wired collector produces ingest_run entries
- powops shows green for all active sources
- Daily pipeline runs automatically (cron/systemd)

### Phase 1 — Signals Work (the measurements exist)
- All 10 signals produce non-None output for all 25 tickers
- Daily state table has real data (not mostly NULL)
- Entity resolution links directors across companies
- Short interest matching is accurate (ISIN + name)

### Phase 2 — The Thesis Can Be Tested (the experiment runs)
- Constraint data from powuk flows into powk
- powk builds historical snapshots
- Seesaw model computes: "Did financial markets reprice physical scarcity before or after the constraint data?"
- At least one counterfactual experiment completed

### Phase 3 — Commercial Value (someone pays)
- UK robotics parts intelligence product
- Repair outcomes data product
- powops is the ops layer for a real business

---

## Phase 0: Data Flow — Get the Tape Working

> Priority: CRITICAL. Duration: 1-2 weeks. Unblock everything else.

### 0.1 Price History Backfill (UNBLOCKS 4 SIGNALS)

**Problem:** `price_daily` has 24 rows (1 day). Momentum signals need 200+ days.

**Action:**
- Run `scripts/backfill_prices.py` for all 25 tickers
- Target: 2+ years of daily OHLCV per ticker
- Verify: `SELECT ticker, COUNT(*), MIN(date), MAX(date) FROM price_daily GROUP BY ticker`

**Why first:** Without historical prices, 4 of 10 signals are dead. This is a 30-minute fix that unblocks half the analysis layer.

**Owner:** powstock
**Blocked by:** Nothing
**Blocks:** price_momentum_50d, price_momentum_200d, moving_average_crossover, drawdown_from_peak

### 0.2 Insider Data for Universe Tickers (UNBLOCKS 4 SIGNALS)

**Problem:** Investegate PDMR collector returns global feed. All 4 deals in DB are for GTE (Gran Tierra), not our 25 stocks.

**Action:**
1. Get Tracefour API key (free, https://www.tracefour.com)
2. Wire `powstock/collectors/tracefour.py` as primary PDMR source
3. Filter to universe tickers only
4. Verify: `SELECT ticker, COUNT(*) FROM insider_deals WHERE ticker IN (SELECT ticker FROM universe) GROUP BY ticker`

**Why second:** Without universe insider data, `insider_pressure`, `alignment_score`, `anomaly_score`, and `composite_score` signals return None. The "who knew, who moved capital" question can't be answered.

**Owner:** powstock
**Blocked by:** Tracefour API key (needs human to register)
**Blocks:** insider_pressure, alignment_score, anomaly_score, composite_score

### 0.3 Fix Blocked Collectors (GET POWOPS GREEN)

**Problem:** 10 of 18 powstock sources show `not_installed` in powops.

**Actions by category:**

**Missing API keys (set env vars):**
- `companies_house` → set `POWSTOCK_COMPANIES_HOUSE_API_KEY`
- `companies_house_filings` → same key
- `finnhub` → set `FINNHUB_API_KEY`

**Network/timeout fixes:**
- `uk_parliament` → increase httpx timeout to 30s, add retry
- `congress_trades` → increase timeout, add retry
- `european_insiders` → API URL changed, fix parser
- `dmo_gilts` → add Cloudflare bypass (cookies or proxy)
- `fca_nsm` → add retry with backoff
- `ch_company_snapshot` → increase timeout for large download
- `ch_accounts_bulk` → same
- `companies_house_psc` → same

**Target:** All 18 powstock sources show `ok` or `stale` (not `not_installed` or `unknown`) in powops.

**Owner:** powstock
**Blocked by:** API keys (human), network access (may need proxy)
**Blocks:** Full powops visibility

### 0.4 Daily Pipeline Automation

**Problem:** `run_all()` only runs when someone manually executes it. No cron, no systemd timer.

**Action:**
- Create systemd timer: `powstock-collect.service` + `powstock-collect.timer`
- Run every 4 hours (prices once/day, RNS every 6h, others daily)
- Write heartbeat.json on each run
- powops monitors the heartbeat

**Target:** Data refreshes automatically without human intervention.

**Owner:** powstock
**Blocked by:** Nothing
**Blocks:** Data freshness, powops staleness alerts

### 0.5 Fix powpowpow Derived State Services

**Problem:** 6 systemd services failing in powpowpow.

**Action:**
- Fix daily-state, qubic-computors, qubic-epoch, seed-rebuild, tardis-reload, tardis-remainder
- These compute derived state from raw collection — they're the Layer 2 of powpowpow

**Owner:** powpowpow
**Blocked by:** Need to inspect service logs
**Blocks:** Derived state computation

---

## Phase 1: Signals Work — The Measurements Exist

> Priority: HIGH. Duration: 2-4 weeks. After Phase 0.

### 1.1 Short Interest Universe Matching

**Problem:** Only CNA matched to universe. FCA XLSX uses different ISIN formats.

**Action:**
- Build ticker-to-ISIN mapping table from universe.py
- Match short_interest by ISIN (primary) and company name (fallback)
- Verify: `SELECT COUNT(DISTINCT ticker) FROM short_interest WHERE ticker IN (SELECT ticker FROM universe)`

**Owner:** powstock
**Blocked by:** 0.1 (price data), 0.2 (insider data)
**Blocks:** short_interest_level, short_squeeze_risk accuracy

### 1.2 Financial Fundamentals (XBRL Parser)

**Problem:** No revenue, cash, debt, employees data. Daily state is mostly NULL.

**Action:**
- Install `stream-read-xbrl` dependency
- Implement `powstock/collectors/financials.py`
- Parse Companies House iXBRL accounts
- Populate: revenue, operating_profit, total_assets, cash, debt, employees

**Why now:** Without fundamentals, the "capital response" part of the thesis can't be measured. Companies raising capital or cutting costs is invisible.

**Owner:** powstock
**Blocked by:** 0.3 (CH API key working)
**Blocks:** Daily state completeness, capital response index

### 1.3 Entity Resolution

**Problem:** `entity_resolver.py` is dead code. Can't link directors across companies.

**Action:**
- Fix httpx import bug (line 191)
- Wire into daily pipeline
- Build person → companies graph
- Store in `entity_resolution` table

**Why now:** The "who knew, who moved capital" question requires linking a person's activities across multiple companies. Without this, you can only see insiders at one company at a time.

**Owner:** powstock
**Blocked by:** 0.2 (insider data for universe tickers)
**Blocks:** Cross-company insider analysis, director network

### 1.4 Signal Validation

**Problem:** 10 signals exist but most return None. Need to verify they produce meaningful output.

**Action:**
- Run all 10 signals against current data
- Document which produce non-None output
- Fix any that should work but don't
- Create `signals_report.md` with results

**Owner:** powstock
**Blocked by:** 0.1, 0.2, 1.1, 1.2
**Blocks:** Experiment readiness

### 1.5 powuk Constraint Collectors

**Problem:** powuk has 0/8 sources. No constraint data exists.

**Action:**
- Implement NESO demand/generation collector (free API, hourly)
- Implement PV Live collector (free API, hourly)
- Implement planning applications collector
- Store in powuk DB with proper schema

**Why now:** The seesaw thesis requires constraint data to compare against financial data. Without powuk, there's nothing to compare.

**Owner:** powuk
**Blocked by:** Nothing (APIs are free)
**Blocks:** Seesaw experiment, powk snapshots

---

## Phase 2: The Thesis Can Be Tested

> Priority: MEDIUM. Duration: 1-2 months. After Phase 1.

### 2.1 powk Snapshot Building

**Problem:** powk has the code to build historical snapshots but no data flowing through it.

**Action:**
- Wire powstock data → powk nodes/edges/observations
- Wire powuk data → powk constraint nodes
- Build daily snapshots for past 6 months
- Verify: `snapshot = graph.build_snapshot(at="2026-03-01")` returns real data

**Owner:** powk
**Blocked by:** 1.5 (powuk data), 0.1 (price history)
**Blocks:** Model execution, counterfactuals

### 2.2 Seesaw Model

**Problem:** The core thesis has no implementation.

**Action:**
- Define the "constraint pressure" model in powk
- Input: powuk constraint observations (demand, capacity, lead times)
- Input: powstock financial observations (insider deals, short interest, prices)
- Output: "Did financial markets reprice before or after the constraint?"
- Compute lead/lag analysis

**Owner:** powk + powstock
**Blocked by:** 2.1 (snapshots), 1.4 (signals working)
**Blocks:** Thesis validation

### 2.3 First Experiment

**Problem:** No experiment has been run. The thesis is untested.

**Action:**
- Pick one constraint: UK transformer supply (from powuk NESO data)
- Pick one signal: insider buying at transformer-adjacent companies (from powstock)
- Measure: Did insiders buy before transformer lead times increased?
- Record in `experiments/` with full provenance

**Owner:** powk
**Blocked by:** 2.2 (model), 1.3 (entity resolution)
**Blocks:** Thesis validation, publication

### 2.4 powops Coverage and Alerting

**Problem:** powops monitors health but not completeness. No webhook alerts.

**Action:**
- Add coverage view: "N of M planned sources actually collecting"
- Configure webhook alerts (Telegram, Discord, or email)
- Add backup status view
- Add source detail drill-down

**Owner:** powops
**Blocked by:** 0.3 (all sources green)
**Blocks:** Operational awareness

---

## Phase 3: Commercial Value

> Priority: LOW. Duration: 3-6 months. After Phase 2.

### 3.1 UK Robotics Parts Intelligence

**Problem:** No product exists. The commercial thesis is unvalidated.

**Action:**
- Implement powproducts collectors (RobotShop, PCI IDs, ROBOTIS)
- Build canonical product identity graph
- Add compatibility data (what fits what)
- Add pricing data (what costs what)
- Build API for product lookup

**Owner:** powproducts
**Blocked by:** Nothing (can start in parallel)
**Blocks:** Commercial product

### 3.2 Supply Chain Intelligence

**Problem:** No visibility into UK robotics import/export.

**Action:**
- Implement powrobots collectors (HMRC, UKRI, RBTX, Mouser, Farnell)
- Build trade flow analysis
- Identify bottleneck components
- Track price trends

**Owner:** powrobots
**Blocked by:** API keys (Mouser, Farnell, LCSC, eBay)
**Blocks:** Commercial product

### 3.3 Repair Outcomes Data

**Problem:** repair garden has data but no product.

**Action:**
- Package Open Repair data as API
- Add eBay UK parts pricing
- Build "what breaks, what gets fixed" analysis
- Sell to repair businesses, insurers, manufacturers

**Owner:** repair
**Blocked by:** Nothing (data exists)
**Blocks:** Revenue

---

## Cross-Cutting Concerns

### Testing

**Current:** 31 tests in powstock, 69 in powops.

**Needed:**
- Integration tests: run_all() → DB → powops status
- Signal tests: verify each signal produces non-None output
- powk tests: snapshot building with real data
- E2E tests: collect → analyze → experiment

### Documentation

**Current:** DEVPLAN.md, ARCHITECTURE.md, SPEC.md, POWOPS_INTEGRATION.md, DEVPLANRESPONSE.md.

**Needed:**
- API reference for each collector
- Signal computation docs
- powk model specification
- Experiment methodology

### Monitoring

**Current:** powops monitors 46 sources across 7 gardens.

**Needed:**
- Webhook alerts when sources go stale
- Coverage dashboard (N of M collecting)
- Backup verification
- Source detail drill-down

### Security

**Current:** Token-gated dashboard, CSP headers, .env for secrets.

**Needed:**
- Rotate tokens regularly
- Cloudflare Access in front of dashboard
- API rate limiting
- Input validation on all endpoints

---

## Milestones

| Milestone | Target | What It Means |
|-----------|--------|---------------|
| M0: Backfill prices | Week 1 | 25 tickers × 2 years of daily OHLCV |
| M1: Tracefour wired | Week 1 | Insider deals for universe tickers |
| M2: All sources green | Week 2 | powops shows 18/18 ok or stale |
| M3: Daily pipeline | Week 2 | Automated collection, no manual runs |
| M4: Signals validated | Week 4 | All 10 signals produce output |
| M5: powuk collecting | Week 4 | NESO demand/generation flowing |
| M6: First snapshot | Week 6 | powk builds real historical snapshot |
| M7: First experiment | Week 8 | Seesaw thesis tested on one constraint |
| M8: Coverage dashboard | Week 8 | powops shows N of M per garden |
| M9: Commercial MVP | Month 4 | UK robotics parts API |

---

## Resource Requirements

### API Keys (free)
- [ ] Tracefour API key (insider data)
- [ ] Finnhub API key (backup insider data)
- [ ] Companies House API key (filings, bulk downloads)

### Compute
- Current VPS: adequate for current load
- When all gardens collect: may need more disk (4.2GB powstock DB, growing)
- powk snapshots: CPU-intensive, may need batch scheduling

### Human Time
- Phase 0: 2-3 days (backfill, wire tracefour, fix blockers)
- Phase 1: 1-2 weeks (financials, entity resolver, powuk collectors)
- Phase 2: 2-4 weeks (powk integration, model, experiment)
- Phase 3: 1-3 months (commercial products)

---

## What NOT to Build

1. **More architecture** — The layered design is done. Stop designing, start collecting.
2. **More signals** — 10 signals exist, 2 work. Fix the data, not the signals.
3. **More gardens** — powproducts and powrobots are empty shells. Get powstock and powuk working first.
4. **More dashboards** — powops has 9 tabs. The problem isn't visibility, it's data.
5. **ML models** — Too early. Get the measurements right first.
6. **Trading logic** — Not the goal. The goal is measurement, not execution.

---

## The One Thing That Matters Most

**Get Tracefour API key → wire insider data for 25 universe tickers → run price backfill → test one signal.**

That's it. That's the entire plan in one sentence. Everything else is infrastructure around that core data flow.

If insiders at transformer-adjacent companies bought before transformer lead times increased, the seesaw thesis has evidence. If they didn't, it doesn't. Either way, we learn something.

The architecture is solid. The monitoring is in place. The signals are coded. Now we need the data to flow through all of it.
