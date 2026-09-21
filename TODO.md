# TODO

## Done
- [x] Universe defined (25 securities)
- [x] Causal graph mapped
- [x] Source registry created
- [x] Price collector (Stooq)
- [x] Insider dealing collector (FCA PDMR)
- [x] Short interest collector (FCA ANSP)
- [x] RNS announcement collector (LSE/FCA)
- [x] Companies House collector (REST API)
- [x] Unified runner with SQLite storage

## Next
- [ ] Test collectors on live data
- [ ] Add ticker→ISIN mapping (OpenFIGI or manual)
- [ ] Build signal framework (z-scored, versioned, provenance)
- [ ] Build daily state builder
- [ ] Companies House financial extraction (XBRL/iXBRL)
- [ ] Yahoo Finance fallback for prices
- [ ] Physical-reasoning compiler

## Later
- [ ] L2 order book (IBKR)
- [ ] FCA Register integration
- [ ] Short interest historical tracking
- [ ] Officer network analysis
- [ ] fish integration (strategies, ensemble, MCP)
