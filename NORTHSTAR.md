# North Star

## The One-Line Version

UK-listed physical-economy data garden. Sensors on every node of the compute-power-materials supply chain.

## The Thesis

London is unusually rich in **power, physical infrastructure, strategic materials, industrial electronics, and small-cap bottleneck names** rather than just software. Every node in the physical compute supply chain has a UK-listed security you can observe.

The L2 order book on a £38m AIM stock (Helium One) contains more information about physical scarcity repricing than the order book on National Grid. Thinner markets are better sensors.

## What We're Building

A continuously-growing, provenance-preserving historical model of how physical constraints get repriced through UK-listed equities.

Not a trading system. A **measurement system** that happens to produce tradeable signals.

## The Causal Graph

```
mineral availability (PRE, TUN, ALL, HE1, RHL, SML)
       ↓
components (IQE, TTG, DSCV)
       ↓
power electronics (XPP)
       ↓
compute hardware (RPI, CNC, SOLI)
       ↓
datacentre deployment (CCC)
       ↓
powered land (BBOX)
       ↓
grid connection (NG., SSE)
       ↓
electricity generation (DRX, CNA)
       ↓
compute economics (CCC, RPI)
```

Every node has a UK-listed security. The L2 feed is a sensor on every node of this graph.

## The Key Question

> Does the financial market reprice physical scarcity before or after the underlying constraint data?

That is the Seesaw thesis applied to UK equities. Every experiment in powstock should ultimately serve this question.

## Success Criteria

1. **25 securities tracked** with daily OHLCV, L2 snapshots, and fundamental data
2. **5+ signals** with provenance, versioning, and cross-sectional z-scores
3. **1+ experiment** showing lead/lag between physical constraint data and equity repricing
4. **MCP server** exposing all UK stock data to agents
5. **fish integration** — strategies running on powstock data, ensemble voting on UK universe

## What Makes This Different

- **Physical reasoning**: Not just price-volume. The signal chain starts with physical constraints (tungsten scarcity, helium supply, grid capacity) and ends with equity repricing.
- **Provenance**: Every observation carries its source, confidence, version, and evidence IDs. No black boxes.
- **Thin markets as sensors**: AIM stocks with £38m market cap are better sensors of physical scarcity than FTSE 100 names.
- **The graph**: Not a watchlist. A causal graph where each node senses a different physical constraint.

## Timeline

- **Week 1**: Stooq price feed, universe registry, basic warehouse
- **Week 2**: FCA PDMR insider dealing, RNS announcements
- **Week 3**: L2 order book (if IBKR access ready)
- **Week 4**: First signal (l2_information_v1), first backtest
- **Month 2**: Physical-reasoning compiler, Companies House financials
- **Month 3**: fish integration, MCP server, first experiment results
