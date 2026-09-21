# TODO

## Done
- [x] Universe defined (25 securities)
- [x] Causal graph mapped
- [x] Source registry created
- [x] Price collector (Yahoo Finance — works, 24/25 tickers)
- [x] Insider dealing collector (FCA PDMR — code ready, needs live test)
- [x] Short interest collector (FCA ANSP — works, 421 positions, 17 universe matches)
- [x] RNS announcement collector (Investegate — works, tested with SSE/CNA)
- [x] Companies House collector (REST API — works, tested with NG.)
- [x] Unified runner with SQLite storage

## Next
- [ ] Test full collector run (run_all)
- [ ] Build ticker→ISIN mapping for better short interest matching
- [ ] Companies House financial extraction (XBRL/iXBRL parsing)
- [ ] Build signal framework (z-scored, versioned, provenance)
- [ ] Build daily state builder

## Later
- [ ] L2 order book (IBKR)
- [ ] FCA Register integration
- [ ] Officer network analysis
- [ ] fish integration (strategies, ensemble, MCP)
