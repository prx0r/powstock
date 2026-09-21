# TODO

## Done
- [x] Universe defined (25 securities)
- [x] Causal graph mapped
- [x] Source registry created
- [x] Price collector (Yahoo Finance — works, 24/25 tickers)
- [x] Insider dealing collector (FCA PDMR — code ready, needs live test)
- [x] Short interest collector (FCA ANSP — code ready, needs live test)
- [x] RNS announcement collector (LSE/FCA — code ready, needs live test)
- [x] Companies House collector (REST API — works, tested with NG., SSE, DRX)
- [x] Unified runner with SQLite storage

## In Progress
- [ ] Test FCA PDMR collector on live data
- [ ] Test FCA short interest collector on live data
- [ ] Test RNS collector on live data
- [ ] Build ticker→ISIN mapping (for short interest matching)

## Next
- [ ] Companies House financial extraction (XBRL/iXBRL parsing)
- [ ] Build signal framework (z-scored, versioned, provenance)
- [ ] Build daily state builder
- [ ] Physical-reasoning compiler

## Later
- [ ] L2 order book (IBKR)
- [ ] FCA Register integration
- [ ] Short interest historical tracking
- [ ] Officer network analysis
- [ ] fish integration (strategies, ensemble, MCP)
