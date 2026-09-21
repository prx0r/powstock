# Architecture

powstock is a data garden. fish is the consumer product on top.

## Repo Relationships

```
powpowpow (crypto data garden)
  ├── core transport layer (auto-archiving fetch, bitemporal, content-addressed)
  ├── warehouse (raw + normalized + parquet)
  ├── signal framework (cross-sectional z-scores with provenance)
  ├── datagarden primitives (Observation, DerivedFact, Source, QualityGate)
  └── experiment registry (hypotheses frozen, never rewritten)

powuk (UK physical infrastructure)
  ├── Companies House SDK (REST + Document + Streaming + Bulk)
  ├── constraint model (Constraint, Opportunity, Severity)
  ├── UK regions (12 GSP/DNO regions with lat/lon)
  ├── shadow price LP solver
  ├── technology diffusion S-curve model
  ├── lag scanner (lead/lag detection)
  ├── scenario engine (shock propagation)
  └── 13+ running collectors (grid, trades, planning, procurement)

fish (trading system — becomes consumer product)
  ├── strategy engine (35+ strategies, 5 animal classes)
  ├── ensemble voting
  ├── walk-forward backtest
  ├── judge system (PSR, DSR, PBO, bootstrap)
  ├── MCP server
  └── Stooq price data (already has .uk symbol support)

powstock (this repo — new)
  ├── UK stock collectors (price, L2, RNS, insider, fundamentals)
  ├── physical-reasoning compiler
  ├── signal adaptation (pow signals → equity signals)
  └── universe registry (25 securities with causal graph tags)
```

## What powstock Imports

### From fish (direct reuse)
- `fish/services/prices.py` — Stooq `.uk` symbol mapping (just populate the dict)
- `fish/fish/strategies/` — all 35+ strategies (exchange-agnostic, work on OHLCV)
- `fish/fish/services/backtest.py` — walk-forward backtest engine
- `fish/fish/services/judge_v2.py` — statistical prosecutor
- `fish/fish/services/online_ensemble.py` — adaptive strategy weighting
- `fish/fish/mcp_server.py` — MCP tools (extend with UK stock tools)

### From powpowpow (pattern reuse)
- `core.py` — auto-archiving `fetch_json`, content-addressed hashing, bitemporal timestamps
- `warehouse.py` — three-tier storage (hot 7d, parquet forever)
- `signals.py` — cross-sectional z-score framework with minimum cross-section requirement
- `datagarden/core/` — Observation, DerivedFact, Source, QualityGate, Receipt
- `experiments.py` — hypothesis registry (frozen, never rewritten)
- `backtest.py` — walk-forward validation, sign-stability diagnostics

### From powuk (UK infrastructure)
- `sdk/companies_house.py` — REST + Document + Streaming API
- `core/constraints.py` — Constraint, Opportunity, Severity model
- `core/regions.py` — 12 UK regions
- `models/shadow.py` — LP dual shadow prices
- `models/lagscan.py` — lead/lag detection
- `models/diffusion.py` — S-curve adoption
- `models/scenario.py` — shock propagation

## What powstock Builds New

### Collectors (see COLLECTORS.md)
- Stooq price feed for UK tickers
- IBKR L2 order book
- RNS announcement feed
- FCA PDMR insider dealing
- Companies House financial extraction (XBRL)
- OpenFIGI security mapping

### Signals
- `grid_constraint_v1` — transmission queue vs capacity
- `material_scarcity_v1` — physical price vs equity repricing speed
- `insider_conviction_v1` — director dealing intensity vs price response
- `l2_information_v1` — order book imbalance on thin AIM stocks
- `compute_deployment_v1` — data-centre announcements vs power names

### Compiler
- `physical_reasoning_compiler.py` — takes raw observations, produces DerivedFacts with provenance
- Maps constraint events to equity nodes via the causal graph
- Tags each signal with: source, confidence, version, evidence IDs

## Data Flow

```
REALITY (LSE, FCA, Companies House, IBKR, Stooq, RNS)
  ↓
COLLECTORS (auto-archiving, content-addressed)
  ↓
WAREHOUSE (raw → normalized → parquet)
  ↓
DAILY STATE BUILDER (one impeccable snapshot per security per day)
  ↓
SIGNALS (cross-sectional, z-scored, versioned, provenance)
  ↓
FACTORS (cross-entity comparison joining STATE + fundamentals + signals)
  ↓
EXPERIMENTS (hypothesis → evaluation with frozen provenance)
  ↓
FISH CONSUMER (strategies, ensemble, backtest, MCP)
```

## Storage

R2 backup via existing Cloudflare credentials:
- Account ID: `954612afb5a97bb15dddcdc70176813d`
- Endpoint: `https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com`
- New bucket: `powstock-garden` (create on first run)
- Layout: `raw/`, `normalized/`, `parquet/`, `signals/`, `experiments/`

## MCP Server Tools (planned)

| Tool | What it reads |
|------|--------------|
| `get_uk_security_state(ticker, date)` | daily_state table |
| `get_uk_signals(ticker, date)` | derived_signal table |
| `get_uk_factors(date)` | cross_security_factors.json |
| `get_causal_graph()` | universe registry with edges |
| `get_insider_activity(ticker)` | director dealings |
| `get_l2_snapshot(ticker)` | order book state |
| `get_rns_recent(ticker)` | recent announcements |
| `get_physical_constraint(constraint_type)` | constraint severity |
| `get_health()` | all warehouse tables |
