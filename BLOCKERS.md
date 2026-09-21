# Blockers → Free Alternatives

Things that were blocked but now have free paths forward.

## ✅ SOLVED — Use These Now

### UK PDMR Insider Data → Tracefour API (FREE)
- **URL**: https://tracefour.com/uk
- **API**: https://tracefour.com/api-docs
- **Status**: ✅ FREE, key required (sign in, no payment)
- **What**: 1.9K UK PDMR filings in 90-day window, refreshed hourly
- **Rate**: 60 requests/hour per key
- **Endpoints**:
  - `GET /v1/eu/uk` — recent UK PDMR filings
  - `GET /v1/filings?direction=P&min_value=100000` — filtered buys
  - `GET /v1/clusters` — cluster buys (3+ insiders same direction)
  - `GET /v1/streaks` — consecutive buying streaks
- **Also has**: SEC Form 4, Congress trades, Germany BaFin, Sweden FI, Netherlands AFM
- **Static exports**: `/data/trackers/{slug}.json` — no key needed, CORS-open

### UK PDMR via AI → ddbx MCP (FREE)
- **URL**: https://ddbx.uk/mcp
- **Status**: ✅ FREE, no key, no sign-in
- **What**: Ask Claude/ChatGPT "What did UK directors buy this week?"
- **Tools**: `search_dealings`, `get_dealing`, `get_company`, `get_daily_summary`
- **Setup**: Add `https://api.ddbx.uk/mcp` as MCP server in Claude/ChatGPT
- **Limitation**: No written analysis (that's the paid product), but has who/what/when/price/value

### UK Company Data → Companies House MCP (FREE)
- **URL**: https://github.com/HelpCode-ai/anythingmcp
- **Status**: ✅ FREE, API key required (register at developer.company-information.service.gov.uk)
- **What**: Search companies, get officers, filing history, charges, PSC
- **Rate**: 600 requests per 5 minutes
- **Key**: Set `POWSTOCK_COMPANIES_HOUSE_API_KEY` in `.env` (register at developer.company-information.service.gov.uk)

### US Insider Data → InsiderGraph (FREE)
- **URL**: https://api.insidergraph.com/v1/ownership?tickers=NVDA
- **MCP**: https://api.insidergraph.com/mcp
- **Status**: ✅ FREE (anonymous: 90-day window, 1 req/s)
- **What**: SEC Form 4 ownership data, insider transactions
- **Free key**: Message @insidergraph_bot on Telegram, send /apikey

### US Insider Data → Finnhub (FREE)
- **URL**: https://finnhub.io/docs/api/insider-transactions
- **Status**: ✅ FREE tier (60 calls/min)
- **What**: `GET /api/v1/stock/insider-transactions?symbol=LSEG.L` — works for UK too
- **Register**: https://finnhub.io/register

## 🔄 ALTERNATIVES — Instead of Paid Blockers

### Instead of ddbx API (private beta) → Use Tracefour + ddbx MCP
- Tracefour gives you the raw PDMR data via API
- ddbx MCP gives you conversational access via Claude
- Together they cover what the paid API would provide

### Instead of Smart Insider (enterprise) → Use Tracefour clusters + streaks
- Tracefour `/v1/clusters` gives cluster buy detection (free)
- Tracefour `/v1/streaks` gives consecutive buying streaks (free)
- These are the key signals Smart Insider charges for

### Instead of LSE RNS Feed (GBP 6.5k/yr) → Use Investegate + Tracefour
- Our Investegate collector already scrapes RNS announcements
- Tracefour has the structured PDMR data from the same source
- Together: free, near-real-time

### Instead of FCA NSM (Cloudflare blocked) → Use Tracefour
- Tracefour scrapes FCA NSM and serves it free via API
- Same data, no Cloudflare headache

### Instead of OpenInsider UK (doesn't exist) → Use Tracefour UK
- OpenInsider is US-only
- Tracefour UK page is the equivalent for UK stocks

## ⚠️ STILL BLOCKED (but less critical)

### XBRL Financial Extraction
- **What**: Parse filed accounts into revenue/profit/employees
- **Status**: No free tool does this well for UK accounts
- **Options**: Arelle (open source), or LLM extraction (slow, expensive)
- **Impact**: Medium — we can get basic company data from Companies House API

### Ticker→ISIN Mapping
- **What**: Match universe tickers to FCA short interest ISINs
- **Status**: Manual mapping needed
- **Options**: Build mapping table from Companies House data, or use OpenFIGI (free, need key)
- **Impact**: Low — we already match by company name

### Real-Time L2 Order Book
- **What**: IBKR Level 2 data for thin AIM stocks
- **Status**: Requires IBKR account + market data subscription
- **Impact**: Low — prices from Yahoo are fine for now

## 📊 FREE DATA SOURCES SUMMARY

| Source | What | Rate | Key? | UK? |
|--------|------|------|------|-----|
| **Tracefour API** | PDMR filings, clusters, streaks | 60/hr | Yes (free) | ✅ |
| **ddbx MCP** | Conversational insider data | Unlimited | No | ✅ |
| **Companies House** | Company profiles, officers, filings | 600/5min | Yes (free) | ✅ |
| **Finnhub** | Insider transactions | 60/min | Yes (free) | ✅ |
| **InsiderGraph** | SEC ownership data | 1/sec | Optional | ❌ (US) |
| **Investegate** | RNS announcements | Scraping | No | ✅ |
| **Yahoo Finance** | OHLCV prices | Rate limited | No | ✅ |
| **FCA ANSP** | Short interest | Daily | No | ✅ |

## 🎯 IMMEDIATE ACTION ITEMS

1. **Get Tracefour API key** — sign in at tracefour.com, create key in Settings
2. **Add ddbx MCP to Claude** — paste `https://api.ddbx.uk/mcp` as connector
3. **Build Tracefour collector** — fetch `/v1/eu/uk` for structured PDMR data
4. **Add Finnhub for UK** — register free, use `?symbol=NG.L` for insider transactions
5. **Build cluster detection** — use Tracefour clusters endpoint for multi-insider buys
