# Collectors

What needs building. Organized by priority.

## P0 — Build First

### 1. Stooq Price Feed
- **Source**: Stooq (free, keyless)
- **Reuse**: `fish/fish/services/prices.py` — already has `.uk` symbol support
- **Work**: Populate `STOOQ_SYMBOLS` with the 25 universe tickers
- **Effort**: Low (30 min)
- **Output**: Daily OHLCV for all 25 securities

### 2. FCA PDMR Insider Dealing
- **Source**: FCA National Statutory Mechanism
- **Work**: New collector — scrape/API FCA PDMR notifications, normalize to director dealing events, link to security by company number
- **Effort**: Medium (1-2 days)
- **Output**: `insider_dealing` table with: ticker, director, action (BUY/SELL/OPTION_GRANT), shares, price, date, filing_url

### 3. RNS Announcement Feed
- **Source**: London Stock Exchange RNS
- **Work**: New collector — RSS/API for RNS announcements, classify by type (trading update, profit warning, board change, contract win, etc.)
- **Effort**: Medium (1-2 days)
- **Output**: `rns_announcements` table with: ticker, title, type, summary, published_at, source_url

### 4. OpenFIGI Security Mapping
- **Source**: OpenFIGI API (free, needs API key)
- **Work**: New collector — map ticker → FIGI → company_number → Companies House
- **Effort**: Low (half day)
- **Output**: `security_mapping` table linking all identifiers

## P1 — Build Next

### 5. IBKR L2 Order Book
- **Source**: IBKR API (requires account + market data subscription)
- **Work**: New collector — subscribe to L2 data for 25 securities, snapshot per minute, store full depth
- **Effort**: High (3-5 days)
- **Output**: `l2_snapshots` table (see L2_STRATEGY.md)

### 6. Yahoo Finance Prices
- **Source**: Yahoo Finance (free, keyless)
- **Work**: New collector — fallback for Stooq, supports `.L` suffix
- **Effort**: Low (half day)
- **Output**: Daily OHLCV backup

### 7. Companies House Financial Extraction
- **Source**: Companies House Document API (already have SDK)
- **Work**: Pipeline — download filed accounts PDFs, extract structured data (revenue, profit, employees) via XBRL parsing or LLM extraction
- **Effort**: High (3-5 days)
- **Output**: `company_financials` table with: company_number, period, revenue, profit_before_tax, employees, filing_date

### 8. FCA Register
- **Source**: FCA Register API
- **Work**: New collector — authorised firms, enforcement actions, regulatory status
- **Effort**: Medium (1-2 days)
- **Output**: `fca_register` table

## P2 — Build Later

### 9. Short Interest
- **Source**: FCA, prime brokers
- **Work**: New collector — short interest data, borrow costs
- **Effort**: Medium

### 10. Institutional Holdings
- **Source**: FCA register, company disclosures
- **Work**: New collector — 13F-style holdings data for UK
- **Effort**: Medium

### 11. ETF/Fund Flows
- **Source**: Fund providers, LSE
- **Work**: New collector — ETF creation/redemption, fund flow data
- **Effort**: Medium

## Collector Pattern

Follow powpowpow's pattern:

```python
# Auto-archiving fetch
result = core.fetch_json(url, headers=headers)
# Every HTTP response auto-archived to warehouse/raw/

# Store normalized
core.store_normalized(table_name, chain_id, data)
# Writes to warehouse/normalized/<table>/chain=<chain>/date=YYYY-MM-DD/

# Daily state builder rolls into one snapshot per security per day
scripts/build_daily_state.py --date 2026-09-21
```

## Registration

Add new collectors to `powstock/collectors/__init__.py`:

```python
from .stooq_prices import StooqPriceCollector
from .fca_pdmr import FcaPdmrCollector
from .rns import RnsCollector
from .openfigi import OpenFigiCollector

COLLECTORS = [
    StooqPriceCollector(interval_seconds=86400),  # daily
    FcaPdmrCollector(interval_seconds=3600),       # hourly
    RnsCollector(interval_seconds=300),             # 5 min
    OpenFigiCollector(interval_seconds=86400),      # daily
]
```
