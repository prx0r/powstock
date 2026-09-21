# powstock

UK-listed physical-economy data garden. Sensors on every node of the compute-power-materials supply chain.

## What This Is

A continuously-growing, provenance-preserving historical model of how physical constraints (grid capacity, semiconductor supply, mineral scarcity, power electronics) get repriced through UK-listed equities.

Not a trading system. A **measurement system** that happens to produce tradeable signals.

## The Thesis

London is unusually rich in **power, physical infrastructure, strategic materials, industrial electronics, and small-cap bottleneck names** rather than just software. Every node in the physical compute supply chain has a UK-listed security you can observe.

The L2 order book on a £38m AIM stock (Helium One) contains more information about physical scarcity repricing than the order book on National Grid. Thinner markets are better sensors.

## Architecture

```
powstock (this repo)
  ├── imports from fish: strategy engine, ensemble, backtest, judge, MCP server
  ├── imports from powpowpow: core transport, warehouse, signal framework, datagarden primitives
  ├── imports from powuk: Companies House SDK, constraint model, UK regions
  └── new: UK stock collectors, L2 feeds, insider dealing, RNS, physical-reasoning compiler
```

**fish becomes the consumer product on top.** powstock is the data garden; fish is the frontend that trades on it.

## Quick Start

```bash
# Clone with fish
git clone https://github.com/prx0r/fish.git
git clone https://github.com/prx0r/powstock.git

# powstock provides the data garden
# fish provides the strategy engine + ensemble + MCP
```

## Status

- [x] Universe defined (25 securities)
- [x] Causal graph mapped
- [ ] Price collectors (Stooq .uk)
- [ ] L2 order book feed (IBKR)
- [ ] RNS announcement collector
- [ ] Insider dealing collector (FCA PDMR)
- [ ] Companies House financial extraction
- [ ] Physical-reasoning compiler
- [ ] Signal framework adaptation
- [ ] Backtest integration with fish

## Docs

- [UNIVERSE.md](UNIVERSE.md) — the 25 securities and why they belong
- [CAUSAL_GRAPH.md](CAUSAL_GRAPH.md) — the physical-economic graph
- [ARCHITECTURE.md](ARCHITECTURE.md) — how it connects to fish/powpowpow/powuk
- [DATA_SOURCES.md](DATA_SOURCES.md) — what's available, what's missing
- [L2_STRATEGY.md](L2_STRATEGY.md) — liquid vs constraint datasets
- [COLLECTORS.md](COLLECTORS.md) — what needs building
