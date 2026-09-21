# powstock

UK-listed physical-economy data garden. Sensors on every node of the compute-power-materials supply chain.

## What This Is

A continuously-growing, provenance-preserving historical archive of UK market, ownership, corporate, and financial reality. The historical state cannot simply be re-scraped later — that's the moat.

**Not a trading system. A measurement system that happens to produce tradeable signals.**

## Architecture

```
powstock/
├── powstock/                ← Core package
│   ├── universe.py          ← 25 securities with hard-coded CH number, ISIN, LEI
│   ├── settings.py          ← pydantic-settings, reads .env
│   ├── schema/              ← Daily state builder
│   ├── collectors/          ← 20 collector modules (6 active, 14 registered)
│   └── entities/            ← Entity resolver (stale, not wired)
│
├── layer1/                  ← Data Garden
│   ├── artifacts.py         ← ArtifactStore (global content-addressed) + IngestRun
│   ├── registry.py          ← Collector registry (manifest-driven execution)
│   ├── health.py            ← 3-level health monitoring (source/ingest/data)
│   └── sources/             ← 16 source manifests (YAML)
│
├── layer2/                  ← Analysis
│   ├── signals/             ← 10 signal functions (insider, short, momentum, alignment)
│   ├── bridge.py            ← powk canonical export (Node, Edge, Observation, Evidence)
│   └── experiments/         ← Empty (Layer 1 must be complete first)
│
├── scripts/
│   ├── daily.py             ← Full pipeline (Layer 1 + optional Layer 2)
│   ├── backfill_prices.py   ← Historical price backfill
│   └── build_daily_state.py ← Daily state materialization
│
├── tests/                   ← 21 tests (replay, idempotence, universe, FK enforcement)
├── data/
│   ├── powstock.db          ← SQLite database (schema v2)
│   └── raw/objects/         ← Content-addressed object store
└── reference/               ← Cloned reference repos
```

## Data Flow

```
REALITY (LSE, FCA, Companies House, Investegate, Yahoo)
  ↓
COLLECTORS (fetch raw bytes)
  ↓
ARTIFACT STORE (SHA256 content-addressed, one object many receipts)
  ↓
INGEST RUN (lifecycle: start → fetch → store → parse → complete)
  ↓
NORMALIZED FACTS (price_daily, insider_deals, short_interest, rns, company_profiles)
  ↓
DAILY STATE (one snapshot per security per day)
  ↓
SIGNALS (cross-source, z-scored, versioned, provenance)
  ↓
EXPERIMENTS (hypothesis → evaluation with frozen provenance)
```

## Sources

| Source | Status | Data | Rows |
|--------|--------|------|------|
| Yahoo Finance | ✅ Working | Daily OHLCV | 5,968 (24 tickers, ~253 days) |
| FCA Short Interest | ✅ Working | Short positions | 421 |
| Investegate RNS | ✅ Working | RNS announcements | 891 |
| Companies House | ✅ Working | Company profiles | 25 |
| Investegate PDMR | ⚠️ Partial | Insider dealing | 25 (non-universe — Tracefour fixes this) |
| Tracefour | 🔑 Needs API key | Structured PDMR, clusters, streaks | — |
| Finnhub | 🔑 Needs API key | SEC insider transactions | — |
| PSC Snapshot | ✅ Built | Persons with Significant Control | — |
| FCA NSM | ✅ Built | Regulatory announcements | — |
| Takeover Panel | ✅ Built | Disclosure forms | — |
| TR-1 Notifications | ✅ Built | Major shareholder changes | — |
| Filing Events | ✅ Built | CH filing → economic events | — |
| CH Company Snapshot | ✅ Built | Full UK company population | — |
| CH Accounts Bulk | ✅ Built | XBRL financial accounts | — |

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Configure API keys
cp .env.example .env
# Edit .env with your keys

# Run all collectors
make run

# Backfill price history
python scripts/backfill_prices.py

# Check health
make health

# Run tests
make test
```

## API Keys (all free)

| Key | Where | What It Unlocks |
|-----|-------|-----------------|
| Companies House | https://developer.company-information.service.gov.uk/ | Company data, officers, filings |
| Tracefour | https://tracefour.com (Sign Up → Settings) | UK insider dealing, clusters, streaks |
| Finnhub | https://finnhub.io/register | SEC insider transactions for UK tickers |

Set in `.env`:
```
POWSTOCK_COMPANIES_HOUSE_API_KEY=your-key
POWSTOCK_TRACEFOUR_API_KEY=your-key
POWSTOCK_FINNHUB_API_KEY=your-key
```

## Storage Model

**Objects** — global, content-addressed, immutable:
```
data/raw/objects/{ab}/{cd}/{sha256}.bin
```
Same bytes stored once. Different runs that fetch identical bytes create new receipts, not new objects.

**Receipts** — per-run observations in SQLite:
```
artifact_receipt: sha256, run_id, source, dataset, retrieved_at
```
One object can have many receipts (same bytes fetched on different days).

**Canonical index** — SQLite, not filesystem:
```
artifact_object: sha256, bytes, content_type, storage_uri, first_seen
```

## The Causal Graph

25 UK-listed securities sensing physical constraints:

```
Physical Materials (PRE, TUN, ALL, HE1, RHL, SML)
    → Semiconductors (IQE)
    → Electronics (XPP, VLX, TTG, DSCV)
    → Compute Hardware (RPI, CNC)
    → Datacentre Deployment (CCC)
    → Powered Land (BBOX)
    → Grid Connection (NG., SSE)
    → Electricity Generation (DRX, CNA)
    → Compute Economics (CCC, RPI)
```

The key question: **Does the financial market reprice physical scarcity before or after the underlying constraint data?**

## Docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design and storage model
- [layer1/README.md](layer1/) — data garden architecture
- [layer2/README.md](layer2/) — signals and analysis
- [UNIVERSE.md](UNIVERSE.md) — the 25 securities
- [CAUSAL_GRAPH.md](CAUSAL_GRAPH.md) — the physical-economic graph
- [COLLECTORS.md](COLLECTORS.md) — collector inventory and status
- [reviews/review3.md](reviews/review3.md) — latest peer review
- [HUMAN_TASKS.md](HUMAN_TASKS.md) — what only humans can do
