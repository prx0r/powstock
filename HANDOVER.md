# HANDOVER.md — powstock

> Last updated: 2026-09-23. Session by: opencode (mimo-v2.5).

---

## What This Repo Is

powstock is a UK physical-economy capital-allocation observatory. It collects data on 25 UK-listed securities that sit at nodes of the physical compute-power-materials supply chain, then computes signals to answer:

> Does the financial market reprice physical scarcity before or after the underlying constraint data?

**Not a trading system. A measurement system that happens to produce tradeable signals.**

---

## Current State (2026-09-23)

### Data
- **11,506** price rows (24/25 tickers, 2 years daily OHLCV)
- **9** insider deals (universe-filtered, Investegate global feed)
- **843** short interest positions (15/25 tickers matched)
- **932** RNS announcements (18 tickers)
- **25** company profiles (all universe companies)
- **5** commodity prices (gold, silver, copper, platinum, palladium)

### Signals Working (9/11)
- `short_interest_level` ✓
- `short_squeeze_risk` ✓
- `filing_event_signal` ✓
- `alignment_score` ✓ (partial — needs insider data)
- `composite_score` ✓
- `price_momentum_50d` ✓
- `price_momentum_200d` ✓
- `moving_average_crossover` ✓
- `drawdown_from_peak` ✓

### Signals Blocked (2/11)
- `insider_pressure` ✗ — no insider deals for universe tickers (needs Tracefour)
- `anomaly_score` ✗ — requires insider data

### Collectors (18 wired, 8 producing data)
| Collector | Status | Records |
|-----------|--------|---------|
| yahoo_finance | ✓ ok | 24 |
| investegate_rns | ✓ ok | 891 |
| companies_house | ✓ ok | 25 |
| investegate_pdmr | ✓ ok | 20 |
| fca_ansp | ✓ ok | 422 |
| takeover_panel | ✓ ok | 1 |
| fca_tr1 | ✓ ok | 30 |
| commodity_prices | ✓ ok | 5 |
| filing_events | ✓ ok | 100 |
| ch_company_snapshot | ○ blocked | 0 |
| ch_accounts_bulk | ○ blocked | 0 |
| companies_house_psc | ○ blocked | 0 |
| finnhub | ○ needs key | 0 |
| tracefour | ○ needs key | 0 |
| uk_parliament | ○ timeout | 0 |
| congress_trades | ○ 403+parse | 0 |
| european_insiders | ○ timeout | 0 |
| dmo_gilts | ○ ShieldSquare | 0 |
| fca_nsm | ○ Cloudflare | 0 |

### Infrastructure
- **powops:** 8/18 sources green, monitoring via collector_db checks
- **API:** FastAPI on port 8797, 15+ endpoints
- **MCP:** 11 tools for powops/agents
- **Systemd:** Automated collection every 4 hours
- **Heartbeat:** Written after each run_all()

---

## How To Run

```bash
cd /root/powstock

# Full pipeline
python3 -c "from powstock.collectors.runner import run_all; run_all()"

# Price backfill
python3 scripts/backfill_prices.py --days 730

# API server
python3 -m powstock.api

# MCP server (stdio)
python3 -m powstock.mcp --stdio

# Tests (non-integration)
python3 -m pytest tests/ -m "not integration"

# Status
python3 -c "from powstock.collectors.runner import status; status()"
```

---

## Key Files

| File | What It Does |
|------|--------------|
| `powstock/collectors/runner.py` | Orchestrator — init_db, run_all, heartbeat |
| `powstock/collectors/__init__.py` | Exports all 20 collectors |
| `powstock/universe.py` | 25 securities with CH#, ISIN, LEI |
| `powstock/api.py` | FastAPI HTTP server |
| `powstock/mcp.py` | MCP tool server |
| `layer1/artifacts.py` | Content-addressed raw storage |
| `layer1/registry.py` | Collector registry (20 collectors) |
| `layer2/signals/__init__.py` | 10 signal functions |
| `scripts/backfill_prices.py` | Historical price backfill |
| `data/powstock.db` | SQLite database |
| `data/heartbeat.json` | Pipeline heartbeat |

---

## Blockers (What Needs Human)

1. **Tracefour API key** — Register at https://www.tracefour.com, set `POWSTOCK_TRACEFOUR_API_KEY` in .env
2. **Finnhub API key** — Register at https://finnhub.io, set `POWSTOCK_FINNHUB_API_KEY` in .env
3. **Proxy for DMO/FCA** — Both behind anti-bot (ShieldSquare/Cloudflare)
4. **Retry logic** — UK Parliament, European Insiders timeout
5. **Congress parser** — XML malformed + CSRF 403

See `BLOCKERS.md` for full details.

---

## What Changed This Session

See `BUILD_NOTES.md` for complete session log.

### Commits (5)
```
6295a5d docs: update BLOCKERS.md — complete list of all blockers
043506b feat: API + MCP server — expose all data via HTTP and MCP
cb012b4 docs: THREADS.md + repo organization fixes
0263e7a docs: BUILD_NOTES.md + CH bulk collector timing fixes
7d8e363 feat: price backfill, insider filtering, short interest matching, systemd timer
```

---

## Next Agent Should

1. Get Tracefour API key (highest impact unblock)
2. Test insider Pressure signal with Tracefour data
3. Wire entity resolver into pipeline
4. Implement powuk collectors (NESO demand/generation — free APIs)
5. Run first seesaw experiment
