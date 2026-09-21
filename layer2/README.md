# Layer 2 — Analysis

Layer 2 consumes Layer 1 data. It does not collect data. It does not depend on fish, powuk, or any other POW.

## Current Implementation

### Signals (`layer2/signals/__init__.py`)

10 signal functions built on Layer 1 observations:

| Signal | Type | Input Tables | What It Measures |
|--------|------|--------------|------------------|
| `insider_pressure` | Single-source | insider_deals | Buying pressure (value/1M, capped at 1.0) |
| `short_interest_level` | Single-source | short_interest | Short positioning (%/20, capped at 1.0) |
| `short_squeeze_risk` | Single-source | short_interest | Same as short interest level |
| `filing_event_signal` | Single-source | company_profiles | Corporate activity intensity |
| `alignment_score` | Cross-source | insider_deals + short_interest | Insiders buying + shorts covering = strong signal |
| `anomaly_score` | Cross-source | insider_deals + short_interest | Divergence between insider and short positioning |
| `composite_score` | Composite | All above | Weighted combination (40% alignment, 25% insider, 20% short, 15% filing) |
| `price_momentum_50d` | Price-based | price_daily | 50-day momentum normalized to 0-1 |
| `price_momentum_200d` | Price-based | price_daily | 200-day momentum |
| `ma_crossover` | Price-based | price_daily | 50/200 day MA ratio |
| `drawdown_from_peak` | Price-based | price_daily | Current drawdown from 52-week peak |

**Key APIs:**
```python
from layer2.signals import compute_all_signals, signal_summary

# Compute all signals for all tickers
signals = compute_all_signals(conn)

# Summary statistics across universe
summary = signal_summary(conn)
```

### POWK Bridge (`layer2/bridge.py`)

Exports powstock data in canonical powk format:

```python
from layer2.bridge import export_all, print_export_summary

export = export_all(conn)
# Returns: {"nodes": [...], "edges": [...], "observations": [...], "evidence": [...]}
print_export_summary(export)
```

**Exports:**
- **Nodes** — universe securities + constraint nodes
- **Edges** — supply chain relationships (REQUIRES)
- **Observations** — prices, short interest, insider deals, company profiles
- **Evidence** — source provenance for each observation type

**Dependency:** Requires `powkernel` (optional). Install with `pip install powstock[k3]`.

## What Belongs Here

- Signal construction from Layer 1 observations
- Backtesting and evaluation
- Cross-domain analysis (does UK grid constraint predict LSE repricing?)
- Experiment tracking
- powk export for downstream consumers

## What Does NOT Belong Here

- Collectors (those are Layer 1)
- Raw data storage (Layer 1)
- Domain-specific scrapers (Layer 1)
- Trading execution (separate repo)
- Dashboards (separate repo)

## Architecture

```
Layer 1 (data garden)
  ├── source manifests
  ├── collectors
  ├── ArtifactStore (content-addressed)
  ├── IngestRun (lifecycle)
  ├── normalized facts (provenance on every row)
  └── health checks

Layer 2 (analysis)  ← you are here
  ├── signals (10 functions)
  ├── bridge (powk export)
  ├── models (compete on same data)
  ├── experiments (versioned, reproducible)
  └── evaluations (which model predicts?)
```

## The Key Distinction

Layer 1 preserves the tape. Layer 2 asks questions about the tape.

Baking the target model into the sensor is a mistake. Layer 1 must remain model-agnostic.
