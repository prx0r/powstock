# Reference Repos — How We Use Each

## Financial Extraction

### stream-read-xbrl (UK Gov Official)
**Use:** Bulk ingestion of Companies House XBRL accounts
**How:**
```python
from stream_read_xbrl import stream_read_xbrl_sync
with stream_read_xbrl_sync() as (columns, date_range_and_rows):
    for (start, end), rows in date_range_and_rows:
        for row in rows:
            # 38 columns: turnover, gross_profit, operating_profit, cash, debt, employees, etc.
```
**Output:** `powstock/data/financials/{company_number}.parquet`

### ixbrl-parse (Lightweight)
**Use:** Parse individual company filings (not bulk)
**How:** `pip install ixbrlparse && ixbrlparse filing.html`
**Output:** Per-filing JSON with all XBRL facts

### uk-accounts-pipeline (Normalisation)
**Use:** Concept aliasing, period selection, provenance tracking
**How:** Copy the `SINGLE_VALUE_SYNONYMS` dict and `_primary_periods()` logic
**Output:** Normalised financials with `reported`/`derived` provenance tags

## Insider Dealings

### insider-scanner (UK RNS/PDMR)
**Use:** Scrape Investegate for PDMR announcements
**How:** Copy `rns_investegate.py` patterns:
- Section-tracking HTML table parser
- `_LABEL_MAP` for field routing
- `_parse_price_volume()` for price/volume extraction
- `_parse_trade_date()` multi-format date parsing
- `normalize_position()` with 85-rule lookup
- `EuropeanInsiderTrade` dataclass
**Output:** `powstock/data/insider_deals/{date}.jsonl`

### insider-scanner (EU Merge)
**Use:** Deduplication with coalescing merge
**How:** Copy `_dedup_key()` and `_coalesce()` from `eu_merger.py`
**Output:** Deduplicated insider trades across sources

## Beneficial Ownership

### bods-stream (PSC Monitoring)
**Use:** Real-time PSC change detection via CH Streaming API
**How:** Copy the streaming consumer pattern:
- Timepoint-based resume
- Exponential backoff with ceiling
- Event isolation (try/except per event)
- Lifecycle state machine (new/updated/closed)
- Risk signals (FATF, trust, nominee, opaque)
**Output:** `powstock/data/psc_events/{date}.jsonl`

### register-ingester-psc (Bulk PSC)
**Use:** Daily PSC snapshot ingestion
**How:** Two-phase pipeline:
1. Download ZIP, split to chunks
2. Ingest with etag-based dedup
**Output:** `powstock/data/psc/{date}/`

## Anomaly Detection

### companieshouse.watch
**Use:** Director velocity, address clustering, officer churn, bulk registration
**How:** Copy the four detector formulas:
```sql
-- Address Cluster
LEAST(100, company_count*2 + recent_90d*4 + shared_directors*8)

-- Director Velocity
LEAST(100, total*5 + recent_90d*5 + recent_30d*10)

-- Officer Churn
LEAST(100, churn*8 + terminations*5)

-- Bulk Registration
LEAST(100, count*5 + recency_bonus(25/10/0))
```
**Output:** Anomaly scores per company, per person

## Company Data

### companies-house-mcp
**Use:** Self-registering tool pattern, rate limiter, dual-content results
**How:** Copy the architecture, not the TypeScript code:
- Tool registry pattern
- Zod-style input validation
- Coverage tracking
- Structured error results

### companies-house-api-python-starter
**Use:** Auth, rate limiting, pagination patterns
**How:** Already adopted:
- `auth=(key, "")` Basic Auth
- Server-guided `Retry-After` backoff
- Offset-based pagination
- Structured error returns

### chwrapper
**Use:** Clean Python CH API client
**How:** Reference for our `companies_house.py` — verify we handle edge cases

### uk-companies-house-parsers-public
**Use:** Parse bulk .dat files (Product 195, 216, 199, etc.)
**How:** Already implemented in `ch_bulk_parsers.py`

### uk-parliament-interests-tracker
**Use:** MP shareholdings data
**How:** Scrape for MP financial interests including shareholdings
**Output:** `powstock/data/mp_interests/{date}.jsonl`

## Data Garden Integration

```
STREAMING LAYER:
  bods-stream → PSC changes (real-time)
  CH Streaming → filings, officers (real-time)
  Investegate → RNS/PDMR (polling)

BULK LAYER:
  stream-read-xbrl → financials (daily/weekly)
  register-ingester-psc → PSC snapshots (daily)
  ch_bulk_parsers → officer history (on request)

TRANSFORMATION LAYER:
  insider-scanner patterns → insider conviction scoring
  companieshouse.watch patterns → anomaly detection
  uk-accounts-pipeline patterns → financial normalisation

OUTPUT LAYER:
  pow_company_state_daily → daily state per company
  entity_graph → person→company relationships
  anomaly_scores → risk signals
  conviction_scores → insider signal strength
```
