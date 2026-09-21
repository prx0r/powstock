# Proposal — Next Development Steps

**Date:** 2026-09-21
**Status:** Proposal
**Author:** opencode

---

## Current State

Layer 1 is mostly working but has three data gaps that block the entire thesis:

| What | Status | Impact |
|------|--------|--------|
| Prices (Yahoo) | 5,968 rows, 23 tickers, ~250 days | Ready |
| Short interest (FCA) | 1,263 rows, 14 universe matches | Ready |
| Company profiles (CH) | 25/25 tickers | Ready |
| Insider deals (Investegate) | 30 rows, **all non-universe stocks** | Blocked |
| RNS announcements | 2 rows total | Blocked |
| Experiments | 0 executed | Blocked |
| Cross-source signals | Can't compute (no insider data) | Blocked |

**The critical insight from this review:** The raw preservation fix and RNS parser fix are done. The remaining blocker is **insider data for universe tickers**. The Investegate PDMR collector fetches the global feed, not our 25 stocks. Tracefour API is the free solution.

---

## Phase 1 — Fix the Three Gaps (1-2 days)

### 1.1 Wire Tracefour for Universe Insider Data

The Investegate PDMR collector scrapes a global feed and picks up non-POW companies (Gran Tierra, KIE, etc.). Tracefour provides structured UK PDMR data via free API.

**What to build:**
- `tracefour_collector.py` — fetches `/v1/eu/uk`, filters to universe tickers via company name lookup
- Store raw JSON via ArtifactStore, normalize to `insider_deals` table
- Add cluster detection via `/v1/clusters` endpoint (3+ insiders same direction = signal)
- Add streak detection via `/v1/streaks` endpoint (consecutive weeks of buying)

**Why this matters:** Without universe insider data, `insider_pressure`, `alignment_score`, `anomaly_score`, and `composite_score` signals are all empty. The cross-source signals are the garden's value proposition.

### 1.2 Verify RNS Works End-to-End

The Investegate direct company page fix is in place but hasn't been validated against the live DB.

**What to do:**
- Run `run_rns()` against all 25 tickers
- Verify `rns_announcements` table has >50 rows
- Spot-check 5 tickers to confirm headlines match Investegate

### 1.3 Clean Dead Code

Remove files that depend on missing dependencies or hardcoded paths:
- `powuk_integration.py` (hardcodes `/root/powuk`)
- `financials.py` (needs `stream-read-xbrl`, not installed)
- `transforms/anomalies.py` (replaced by Layer 2 signals)
- `transforms/conviction.py` (arbitrary weights, quarantined)

---

## Phase 2 — First Experiment (3-5 days)

### 2.1 The Thesis to Test

> Does the financial market reprice physical scarcity before or after the underlying constraint data?

**Hypothesis H001:** Insider buying in physical-materials companies (TUN, HE1, PRE, ALL) precedes equity repricing by N days.

**Why this experiment first:**
- Tungsten West (TUN) has the clearest physical chain: Chinese export policy → tungsten spot price → western scarcity → TUN valuation
- Helium One (HE1) and Rift Helium (RHL) provide **within-domain replication** — two separate helium companies
- Insider buying data is free via Tracefour
- Price data already exists (250+ days)

**What to build:**
- `experiments/lead_lag_insider.py` — for each materials ticker:
  1. Find insider purchase events (date, value, director role)
  2. Measure price change at +1d, +3d, +7d, +14d, +30d after purchase
  3. Compare to matched control window (same length, no insider event)
  4. Compute bootstrap confidence interval on the difference
  5. If CI excludes zero → insider buying precedes repricing

**Statistical standard:** Wilson score interval on proportion. No bootstrap overkill. Cluster by intent × model (per AGENTS.md).

### 2.2 Cross-Sectional Signal Validation

Once insider data exists, compute all 10 signals and validate:

- `composite_score` — the weighted composite should show meaningful variance across the 25 tickers
- `alignment_score` — cross-source signal (insider + short interest) should be >0 for at least some tickers
- Price momentum signals — verify 50d and 200d momentum are computed correctly

**What to build:**
- `scripts/compute_signals.py` — runs `signal_summary(conn)` and saves results to `data/signals/`
- `scripts/validate_signals.py` — checks signals for NaN, zero-variance, and expected distributions

---

## Phase 3 — Layer 2 Completeness (1-2 weeks)

### 3.1 Daily State Materialization

The `build_daily_state.py` script works but produces sparse states (most fields are NULL because financial data isn't available).

**What to build:**
- Wire FCA TR-1 notifications to ownership_delta fields
- Wire filing events to director_join/leave counts
- Add price-derived fields (market_cap from price × shares outstanding, volatility from 20d rolling std)

### 3.2 L2 Order Book (Optional, Lower Priority)

L2 data requires IBKR account + market data subscription. The `L2_STRATEGY.md` defines three signals:
- `l2_information_v1` — spread × imbalance
- `l2_liquidity_v1` — depth
- `l2_withdrawal_v1` — quote withdrawal count

**Decision needed:** Is IBKR access available? If not, skip L2 and focus on what's free.

### 3.3 MCP Server

Expose powstock data to agents via MCP:
- `get_uk_security_state(ticker, date)` — daily_state table
- `get_uk_signals(ticker, date)` — derived_signal table
- `get_uk_factors(date)` — cross_security_factors.json
- `get_causal_graph()` — universe registry with edges
- `get_insider_activity(ticker)` — director dealings
- `get_health()` — all warehouse tables

**Why MCP matters:** Enables other agents (fish, hermes, etc.) to query powstock data programmatically. This is how powstock becomes useful beyond its own experiments.

---

## Phase 4 — fish Integration (Later)

fish has 35+ strategies, ensemble voting, walk-forward backtest, and a judge system. The integration plan:

1. **Price data** — powstock already has Stooq `.uk` symbol mapping. fish can consume `price_daily` directly.
2. **Strategy engine** — fish strategies are exchange-agnostic OHLCV. They work on powstock data without modification.
3. **Ensemble voting** — run fish's 5 animal classes on powstock universe, let ensemble decide.
4. **Judge system** — PSR, DSR, PBO, bootstrap on powstock strategies.

**Dependency note:** Layer 1 must stay independent of fish (per NEXT_STEPS.md Priority 5). Integration is Layer 2/3.

---

## What NOT to Do

1. **Don't build more signals until insider data works.** The cross-source signals are the value. Single-source signals (price momentum, short interest) are commodities.

2. **Don't add fish/powuk dependencies.** Layer 1 must stay clean. fish is a consumer, not a dependency.

3. **Don't chase L2 order book without IBKR access.** Free data (prices, short interest, insiders, RNS) is sufficient for the first experiment.

4. **Don't over-invest in daily state completeness.** NULL fields are fine. The state is a materialized view, not a truth table. Rebuild from fact tables when needed.

5. **Don't build the Capital Response Index yet.** It requires financial data extraction (XBRL), director network analysis, and capex proxy calculation. That's Phase 4+ territory.

---

## Priority Order

| # | What | Effort | Value |
|---|------|--------|-------|
| 1 | Tracefour insider collector | 1 day | Unblocks 4 signals |
| 2 | Verify RNS end-to-end | 0.5 day | Completes Layer 1 tape |
| 3 | Clean dead code | 0.5 day | Reduces confusion |
| 4 | First experiment (insider lead/lag) | 2-3 days | Tests the thesis |
| 5 | Signal validation suite | 1 day | Proves signals work |
| 6 | Daily state completeness | 2-3 days | Fills NULL fields |
| 7 | MCP server | 2-3 days | Makes data useful to agents |
| 8 | fish integration | 1 week | Strategy engine on powstock data |

**Total estimated effort:** 2-3 weeks for a working system that tests the thesis and produces tradeable signals.

---

## Success Criteria (End of Phase 2)

1. 25 securities tracked with daily OHLCV, insider data, short interest, and RNS
2. 5+ signals computing across the universe with real data
3. 1 experiment showing (or refuting) insider lead/lag on physical-materials tickers
4. All tests passing, `make run` produces clean output
5. The core question answered: **does the market reprice physical scarcity before or after the data?**
