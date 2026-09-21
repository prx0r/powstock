# Data Sources

What exists. What's missing. What needs building.

## What's Available (Free / Cheap)

### Price Data
- **Stooq** — free, keyless, supports `.uk` suffix for LSE stocks. fish already has `STOOQ_SYMBOLS` dict with `"OXIG": "oxig.uk"`. Just add the 25 universe tickers.
- **Yahoo Finance** — free, supports LSE tickers with `.L` suffix. Good fallback.

### Companies House (Already Built in powuk)
- **REST API** — search, company profiles, officers, filings, charges, PSC, insolvency
- **Document API** — metadata + PDF download for filed accounts
- **Streaming API** — real-time events for company changes, filings, officer changes, insolvency, charges, PSC changes
- **Bulk data** — 849,999 companies already downloaded to `/root/ographuk/data/bulk/part1.db`
- **API keys**: REST (`d284d51e...`), Streaming (`0aa57ba1...`)

### UK Regulatory
- **FCA National Statutory Mechanism (NSM)** — regulated firm disclosures, PDMR notifications (insider dealings). Listed in SOURCE_MATRIX as P0 but no collector code exists.
- **RNS (Regulatory News Service)** — company announcements, trading updates, profit warnings. No collector.

### Market Data
- **IBKR L2** — listed in SOURCE_MATRIX as P0, marked "INTERNAL_ONLY pending review". No collector code exists. The £7/month feed for UK market data.

### Open Data
- **OpenFIGI** — security identity mapping (FIGI identifiers). Listed in SOURCE_MATRIX as P0 but no collector.

## What's Missing (Needs Building)

### Price Feed
- No real-time or historical UK equity prices in any of the three repos
- Stooq is the easy win — just populate `STOOQ_SYMBOLS` with the 25 universe tickers
- Yahoo Finance as backup with `.L` suffix

### L2 Order Book
- IBKR is the source (P0 in SOURCE_MATRIX)
- Need: collector for UK market depth, bid/ask, volume, quote updates
- Split into two datasets: `POW_UK_LIQUID` (NG., SSE, DRX, etc.) and `POW_UK_CONSTRAINT` (HE1, TUN, PRE, etc.)

### Insider Dealing
- FCA PDMR database — director dealings notifications
- Companies House streaming captures officer changes (AP01/TM01) but doesn't connect to share dealings
- Need: FCA PDMR collector → normalize → link to security → signal

### RNS Announcements
- The UK's primary source of market-moving corporate announcements
- No collector exists in any repo
- Need: RNS feed → classify by type (trading update, profit warning, board change, etc.) → signal

### Financial Fundamentals
- Companies House SDK can download accounts PDFs but no extraction pipeline
- No XBRL parser, no OCR, no LLM extraction
- Need: PDF → structured data pipeline for revenue, profit, employees, margins

### Short Interest
- FCA, prime brokers
- Not implemented anywhere

### Institutional Holdings
- FCA register, company disclosures
- Not implemented

## Source Priority Matrix

| Source | Priority | Status | Effort |
|--------|----------|--------|--------|
| Stooq prices | P0 | Ready (just populate symbols) | Low |
| Companies House | P0 | Built in powuk | Done |
| IBKR L2 | P0 | Listed, no code | High |
| FCA PDMR (insiders) | P0 | Listed, no code | Medium |
| RNS | P0 | Not listed, no code | Medium |
| OpenFIGI | P0 | Listed, no code | Low |
| Yahoo Finance | P1 | Not listed, no code | Low |
| FCA Register | P1 | Not listed, no code | Medium |
| XBRL extraction | P1 | Not listed, no code | High |
| Short interest | P2 | Not listed, no code | Medium |
| Institutional holdings | P2 | Not listed, no code | Medium |
