# Blockers

Things we can't access right now but would be extremely valuable.

## Critical (Would Transform the System)

### ddbx API (UK PDMR Data)
- **URL**: https://ddbx.uk/developers
- **Status**: Private beta, need API key
- **What**: Every UK PDMR filing parsed, rated, cluster-scored, with written rationale
- **Why**: Best UK insider data source — 15-min ingest cadence, buy-style classification, performance tracking
- **How to get**: Request access at https://ddbx.uk/developers
- **Also has**: Free MCP connector at https://ddbx.uk/mcp (works with Claude/ChatGPT immediately)

### FCA NSM Portal (Raw PDMR Filings)
- **URL**: https://data.fca.org.uk/artefacts/NSM/RNS/
- **Status**: Returns 403 (Cloudflare blocked)
- **What**: The authoritative source for all UK PDMR notifications
- **Why**: Direct access means no scraping dependency on Investegate
- **How to unblock**: Need either: (a) FCA API key, (b) browser automation with Cloudflare bypass, or (c) use ddbx as proxy

### LSE RNS Data Feed (Real-Time)
- **URL**: https://api.rns-distribution.com/
- **Status**: Commercial — GBP 6,500-26,000/year
- **What**: Real-time WebSocket push of all RNS announcements
- **Why**: Instant PDMR notification instead of polling Investegate
- **How to get**: Licence from LSEG (free for private investors with confirmation)

### Smart Insider (Institutional-Grade)
- **URL**: https://www.smartinsider.com/
- **Status**: Enterprise/custom pricing, no self-serve
- **What**: 50,000+ global equities, insider transactions since 2015, 36 countries
- **Why**: Gold standard for institutional insider data, quantitative feeds
- **How to get**: Request trial at https://www.smartinsider.com/request-trial-director-changes

## High Value (Nice to Have)

### Finnhub Insider Transactions
- **URL**: https://finnhub.io/docs/api/insider-transactions
- **Status**: Free tier available (60 calls/min), need API key
- **What**: `GET /api/v1/stock/insider-transactions?symbol=LSEG.L` — UK PDMR data
- **Why**: Structured JSON API, easy to integrate
- **How to get**: Register free at https://finnhub.io/register

### OpenInsider (UK)
- **URL**: http://openinsider.com/
- **Status**: US-only, no UK data
- **What**: fish already has an adapter for US insider trades
- **Why**: Could extend to UK if they add it
- **Note**: Currently only SEC Form 4 data

### InsiderScreener (European)
- **URL**: https://www.insiderscreener.com/en/l/insider-trading-europe
- **Status**: Paid only (EUR 42/month)
- **What**: 12 European markets including UK, live PDMR, director buys/sells
- **Why**: Comprehensive European coverage with API

### InsiderLayer (Multi-Country API)
- **URL**: https://insiderlayer.com/
- **Status**: Free tier with 7-day lag, paid for real-time
- **What**: REST API for 35 countries including UK, standardized schema
- **Why**: Single API for multi-country insider data
- **Also has**: MCP server for AI integration

### Simply Wall St (Ownership Data)
- **URL**: https://simplywall.st/stocks/gb/
- **Status**: Freemium
- **What**: Per-company ownership breakdowns, insider transaction history
- **Why**: Visual ownership analysis, institutional vs insider breakdown

## Technical Blockers

### Companies House Financial Extraction
- **Status**: SDK works, but XBRL parsing not implemented
- **What**: Filed accounts contain revenue, profit, employees, margins
- **Blocker**: Need to parse iXBRL/PDF filings into structured data
- **Options**: Arelle (open source XBRL processor), uk-accounts-pipeline (GitHub), or LLM extraction

### Ticker→ISIN Mapping
- **Status**: No mapping exists in codebase
- **What**: FCA short interest uses ISIN, not tickers
- **Blocker**: Can't reliably match universe tickers to FCA short positions
- **Options**: OpenFIGI API (free, need key), or manual mapping table

### OpenFIGI Security Mapping
- **URL**: https://api.openfigi.com/v3/
- **Status**: Free, need API key
- **What**: Map ticker→FIGI→company_number→Companies House
- **Why**: Cross-referencing all data sources
- **How to get**: Register at https://www.openfigi.com/

## Community/Research Gaps

### No UK Insider Buying Newsletter
- **What exists**: CEO Watcher (US), interactive investor "Insider" column (weekly)
- **What's missing**: Daily UK-specific insider buying analysis
- **Opportunity**: Build this as a powstock output

### No UK Insider Buying Discord/Telegram
- **What exists**: CEO Watcher Discord (US)
- **What's missing**: UK-focused community tracking director buys
- **Opportunity**: Build this around powstock data

### No UK Insider buying backtest research
- **What exists**: TimHanewich/Insider-Buying-Research (US S&P 500, 2010-2019)
- **What's missing**: UK FTSE All-Share equivalent study
- **Opportunity**: powstock can do this with our data
