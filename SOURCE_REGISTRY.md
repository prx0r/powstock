# Source Registry

Every UK data source we can use. What it provides, how to access it, cost, format.

## Tier 0 — Free, No Key, Start Now (TESTED & WORKING)

### Yahoo Finance (PRICES)
- **URL**: `https://query1.finance.yahoo.com/v8/finance/chart/{ticker}.L`
- **Format**: JSON
- **Cost**: Free, no key
- **Coverage**: All LSE stocks (use `.L` suffix for Main Market and AIM)
- **Update**: 15-min delay
- **Use**: OHLCV price history for all 25 universe tickers
- **Status**: ✅ WORKING — 24/25 tickers returning data
- **Note**: RHL (Rift Helium) not yet on Yahoo (too new)

### FCA Short Selling (ANSP)
- **URL**: `https://www.fca.org.uk/publication/documents/aggregated-net-short-positions.xlsx`
- **Format**: XLSX (changed from CSV)
- **Cost**: Free
- **Coverage**: All UK shares with short positions >0.2% of issued capital
- **Update**: Daily from 12:00, T+2
- **Use**: Short interest tracking, changes over time
- **Status**: ✅ WORKING — 421 positions, 17 universe matches (SSE, BBOX, VLX, CCC, NG., CNA, DSCV, IQE, XPP, DRX, SGRO, SML, PRE, RPI)
- **Fields**: ISIN, issuer name, position %, report date

### Companies House Bulk Data — Company Info
- **URL**: `https://download.companieshouse.gov.uk/en_output.html`
- **Format**: CSV in ZIP (~470MB)
- **Cost**: Free
- **Coverage**: ~5 million UK companies
- **Update**: Monthly (within 5 working days of month end)
- **Use**: Company name, number, status, SIC codes, registered office, accounts dates
- **Fields**: CompanyNumber, CompanyName, CompanyStatus, SICCode, RegisteredOfficeAddress, AccountsNextDueDate

### Companies House Bulk Data — PSC Register
- **URL**: `https://download.companieshouse.gov.uk/en_pscdata.html`
- **Format**: JSON
- **Cost**: Free
- **Coverage**: All persons with significant control
- **Update**: Daily before 10am GMT
- **Use**: Ownership concentration, beneficial owner tracking
- **Fields**: company_number, name, nature_of_control, notified_on, ceased_on

### Bank of England — UK Share Prices
- **URL**: `https://www.bankofengland.co.uk/statistics/research-datasets`
- **Format**: XLSX
- **Cost**: Free
- **Coverage**: UK share price index (quarterly, Apr 1962=100)
- **Use**: Long-term market context
- **Also on FRED**: `https://fred.stlouisfed.org/series/SPPUKQ`

### DMO Gilts
- **URL**: `https://www.dmo.gov.uk/`
- **Format**: CSV, XLS
- **Cost**: Free
- **Coverage**: UK gilt yields, treasury bill auctions
- **Update**: Daily
- **Use**: Risk-free rate, yield curve context

---

## Tier 0 — Free, Needs API Key (easy to get)

### Companies House REST API
- **URL**: `https://api.company-information.service.gov.uk/`
- **Format**: JSON REST
- **Cost**: Free (register for API key)
- **Rate limit**: 600 requests per 5 minutes
- **Auth**: HTTP Basic (API key as username, empty password)
- **Key endpoints**:
  - `GET /search/companies?q={name}` — company search
  - `GET /company/{number}` — full profile (status, SIC, accounts dates)
  - `GET /company/{number}/officers` — directors, secretaries
  - `GET /company/{number}/persons-with-significant-control` — PSC
  - `GET /company/{number}/filing-history` — all filings
  - `GET /company/{number}/charges` — mortgages/charges
  - `GET /company/{number}/insolvency` — insolvency records
  - `GET /officers/{officer_id}/appointments` — all companies an officer serves
- **Use**: Company fundamentals, director networks, charge tracking
- **Note**: Set `POWSTOCK_COMPANIES_HOUSE_API_KEY` in `.env`

### Companies House Streaming API
- **URL**: `https://stream.companieshouse.gov.uk/companies`
- **Format**: SSE (Server-Sent Events)
- **Cost**: Free (separate API key)
- **Rate limit**: Max 2 concurrent connections
- **Auth**: HTTP Basic (streaming key as username)
- **Events**: company changes, filings, officer changes, insolvency, charges, PSC changes
- **Use**: Real-time company events feed
- **Note**: Set `POWSTOCK_COMPANIES_HOUSE_API_KEY` in `.env` (separate streaming key)

### OpenFIGI
- **URL**: `https://api.openfigi.com/v3/`
- **Format**: JSON REST
- **Cost**: Free (register for API key)
- **Use**: Map ticker → FIGI → company_number → Companies House
- **Key endpoints**:
  - `POST /v3/mapping` — map identifiers (ticker, ISIN, SEDOL) to FIGI
  - `GET /v3/search` — search by company name
- **Use**: Security identity resolution, cross-referencing

---

## Tier 0 — Free, Needs API Key (TESTED & WORKING)

### Companies House REST API (COMPANY DATA)
- **URL**: `https://api.company-information.service.gov.uk/`
- **Format**: JSON REST
- **Cost**: Free (API key required)
- **Auth**: HTTP Basic (API key as username)
- **Key**: Set `POWSTOCK_COMPANIES_HOUSE_API_KEY` in `.env`
- **Rate limit**: 600 requests per 5 minutes
- **Status**: ✅ WORKING — tested with National Grid, SSE, Drax
- **Key endpoints**:
  - `GET /search/companies?q={name}` — company search
  - `GET /company/{number}` — full profile (status, SIC, accounts dates)
  - `GET /company/{number}/officers` — directors, secretaries
  - `GET /company/{number}/persons-with-significant-control` — PSC
  - `GET /company/{number}/filing-history` — all filings
  - `GET /company/{number}/charges` — mortgages/charges
  - `GET /company/{number}/insolvency` — insolvency records

### Companies House Streaming API
- **URL**: `https://stream.companieshouse.gov.uk/companies`
- **Format**: SSE (Server-Sent Events)
- **Cost**: Free (separate API key)
- **Key**: Set `POWSTOCK_COMPANIES_HOUSE_STREAMING_KEY` in `.env`
- **Rate limit**: Max 2 concurrent connections
- **Events**: company changes, filings, officer changes, insolvency, charges, PSC changes
- **Use**: Real-time company events feed

---

## Tier 1 — Free, But Needs Scraping (TESTED & WORKING)

### Investegate RNS (ANNOUNCEMENTS)
- **URL**: `https://www.investegate.co.uk/Index.aspx`
- **Format**: HTML (table rows with announcements)
- **Cost**: Free
- **Coverage**: All RNS announcements (438+ per day)
- **Update**: Real-time (during market hours)
- **Status**: ✅ WORKING — tested with SSE, CNA, found PDMR/shareholding announcements
- **Use**: Company news, results, profit warnings, board changes, director dealings
- **Fields**: Company name, TIDM, headline, source (RNS/PRN/EQS), time, URL
- **Note**: FCA NSM blocked (403), but Investegate provides same RNS data

### FCA Short Selling (see Tier 0 above)
- **URL**: `https://www.fca.org.uk/publication/documents/aggregated-net-short-positions.xlsx`
- **Status**: ✅ WORKING — XLSX format, 421 positions

### FCA PDMR Notifications (INSIDER DEALING)
- **URL**: `https://data.fca.org.uk/artefacts/NSM/RNS/`
- **Format**: HTML (structured notification forms)
- **Cost**: Free web search
- **Coverage**: All UK listed company director/PDMR trades
- **Update**: Continuous (within 3 business days)
- **Status**: ⚠️ CODE READY — FCA blocks direct access (403), need alternative approach
- **Note**: RNS announcements from Investegate include "Director/PDMR Shareholding" headlines
- **Cost**: Free
- **Coverage**: Same RNS data, official regulatory archive
- **Use**: Backup for LSE RNS, historical search

### Investegate (via Apify)
- **URL**: `https://www.investegate.co.uk`
- **Format**: HTML (scrape via Apify actor)
- **Cost**: $0.05/announcement via Apify
- **Coverage**: RNS aggregated for investor relations
- **Use**: Alternative RNS source with better structure

---

## Tier 2 — Commercial (Budget Required Later)

### LSE RNS Data Feed API
- **URL**: `https://api.rns-distribution.com/`
- **Format**: JSON REST + WebSocket
- **Cost**: GBP 6,500-26,000/year
- **Coverage**: Full RNS feed, real-time
- **Use**: Programmatic RNS access at scale
- **Note**: Not needed initially — scraping covers us

### IBKR L2 Order Book
- **URL**: IBKR TWS/Gateway API
- **Format**: Proprietary (ib_insync library)
- **Cost**: IBKR account + market data subscription (~£7/month for UK)
- **Coverage**: Full L2 depth for LSE, AIM
- **Update**: Real-time
- **Use**: Order book imbalance, spread, depth signals
- **Note**: Last priority — add after basic data pipeline works

---

## Tier 3 — Government/Statistical (Context Data)

### ONS Labour Demand
- **URL**: `https://www.ons.gov.uk/`
- **Format**: XLSX
- **Cost**: Free
- **Coverage**: Job adverts by SOC x region
- **Use**: Labour market context
- **Note**: powuk already collects this

### FCA Transaction Reporting
- **Format**: Internal FCA use only
- **Note**: Individual trade data NOT publicly available

### Takeover Panel Notifications
- **URL**: Published via FCA NSM
- **Format**: RNS announcements
- **Coverage**: Shareholder notifications above thresholds (1%, 2%, 3%, 5%)
- **Use**: Activist/corner situation detection

---

## Collector Implementation Plan

### Phase 1 — Price + Insider + RNS (Week 1)
1. **Stooq prices** — populate `STOOQ_SYMBOLS` with 25 tickers, fetch daily OHLCV
2. **FCA PDMR** — scrape NSM for "Director/PDMR Dealings", normalize to structured events
3. **FCA short interest** — download daily ANSP CSV, track changes

### Phase 2 — Company Fundamentals (Week 2)
4. **Companies House bulk** — download, parse, join with universe
5. **Companies House streaming** — real-time events for universe tickers
6. **OpenFIGI** — map tickers to company numbers

### Phase 3 — News + Context (Week 3)
7. **RNS announcements** — scrape LSE or NSM for universe tickers
8. **DMO Gilts** — download daily yields for risk-free rate
9. **Bank of England** — quarterly share price index

### Phase 4 — L2 (Later)
10. **IBKR L2** — order book data for constraint dataset
