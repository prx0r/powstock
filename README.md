# powstock

UK-listed physical-economy data garden. Sensors on every node of the compute-power-materials supply chain.

## Architecture

```
powstock/
├── layer1/              ← Data Garden
│   ├── sources/         ← per-source manifests + collectors
│   │   ├── yahoo_prices/
│   │   ├── fca_short_interest/
│   │   ├── companies_house/
│   │   ├── fca_pdmr/
│   │   ├── rns_announcements/
│   │   ├── psc_snapshot/
│   │   ├── filing_events/
│   │   └── takeover_panel/
│   ├── manifest_schema.yaml
│   └── health.py
│
├── layer2/              ← Analysis (consumes Layer 1)
│   ├── signals/
│   └── experiments/
│
├── powstock/            ← Core package (collectors, schema, entities)
└── tests/
```

## Layer 1: The Data Garden

Every source has:
- **Manifest** — operational contract (authority, cadence, schema, health thresholds)
- **Collector** — fetches, parses, stores raw bytes
- **Health** — standardized state (last_success, records_seen, staleness)
- **Raw preservation** — append-only, timestamped, content-addressed

No fish dependency. No powuk dependency. No signal logic. Just the tape.

## Layer 2: Analysis

Consumes Layer 1 data. No domain-specific code. No collector logic. Models compete on the same data. Historical data tells us which predicts.

## Quick Start

```bash
pip install -e ".[dev]"

# Check source health
make health

# Run all collectors
make run

# Run tests
make test
```

## Sources

| Source | Authority | Cadence | Data |
|--------|-----------|---------|------|
| yahoo_prices | Yahoo Finance | Daily | OHLCV |
| fca_short_interest | FCA | Daily | Short positions |
| companies_house | Companies House | Daily | Profiles, officers, filings |
| fca_pdmr | Investegate/FCA | Daily | Insider dealings |
| rns_announcements | Investegate/LSE | Daily | RNS announcements |
| psc_snapshot | Companies House | Daily | Persons of Significant Control |
| filing_events | Companies House | Daily | Filing → economic event |
| takeover_panel | Takeover Panel | Daily | Disclosure forms |

## Docs

- [UNIVERSE.md](UNIVERSE.md) — the 25 securities
- [CAUSAL_GRAPH.md](CAUSAL_GRAPH.md) — the physical-economic graph
- [layer1/README.md](layer1/) — Layer 1 architecture
- [layer2/README.md](layer2/) — Layer 2 architecture
- [reviews/review1.md](reviews/review1.md) — peer review
