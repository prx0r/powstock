# POWOPS Integration — powstock

> How powops monitors powstock. Every source, every table, every status.

## Quick Reference

```
powstock DB:   /root/powstock/data/powstock.db
powops config: /root/powops/powops/sources.yaml
Check type:    collector_db (reads ingest_run via collector_run view)
```

## Architecture

```
powstock run_all()
  │
  ├─► IngestRun (per collector)
  │     ├─ ArtifactStore.put_bytes() → data/raw/objects/ (content-addressed)
  │     ├─ INSERT INTO ingest_run    (lifecycle tracking)
  │     ├─ INSERT INTO <table>       (normalized facts)
  │     └─ INSERT INTO collector_state (legacy status)
  │
  ├─► data/heartbeat.json           (for powops heartbeat checks)
  │
  └─► collector_run VIEW            (maps ingest_run → powops schema)
        │
        └─► powops reads via collector_db check
```

## Source Mapping

Every powops `source_id` MUST match the `ingest_run.source` value in powstock.

| powops source_id | ingest_run.source | Collector | Table | powops Status |
|---|---|---|---|---|
| `yahoo_finance` | `yahoo_finance` | `run_prices()` | `price_daily` | ok |
| `investegate_rns` | `investegate_rns` | `run_rns()` | `rns_announcements` | stale |
| `companies_house` | `companies_house` | `run_companies()` | `company_profiles` | no_key |
| `investegate_pdmr` | `investegate_pdmr` | `run_insiders()` | `insider_deals` | ok |
| `fca_ansp` | `fca_ansp` | `run_short_interest()` | `short_interest` | ok |
| `takeover_panel` | `takeover_panel` | `run_takeover_panel()` | (collector_state only) | ok |
| `fca_tr1` | `fca_tr1` | `run_tr1()` | (collector_state only) | ok |
| `commodity_prices` | `commodity_prices` | `run_commodity_prices()` | (collector_state only) | ok |
| `companies_house_psc` | `companies_house_psc` | `run_psc_snapshot()` | (none) | not_installed |
| `ch_company_snapshot` | `ch_company_snapshot` | `run_ch_company_snapshot()` | (none) | not_installed |
| `ch_accounts_bulk` | `ch_accounts_bulk` | `run_ch_accounts_bulk()` | (none) | not_installed |
| `companies_house_filings` | `companies_house_filings` | `run_filing_events()` | (none) | not_installed |
| `finnhub` | `finnhub` | `run_finnhub()` | (none) | not_installed |
| `uk_parliament` | `uk_parliament` | `run_uk_parliament()` | `insider_deals` | not_installed |
| `congress_trades` | `congress_trades` | `run_congress_trades()` | (none) | not_installed |
| `european_insiders` | `european_insiders` | `run_european_insiders()` | (none) | not_installed |
| `dmo_gilts` | `dmo_gilts` | `run_dmo_gilts()` | (none) | not_installed |
| `fca_nsm` | `fca_nsm` | `run_fca_nsm()` | (none) | not_installed |

### Status Definitions

- **ACTIVE (ok)** — has `ingest_run` entries, data confirmed flowing
- **STALE** — has data but older than `max_staleness` threshold
- **NO_KEY** — requires API key that isn't set
- **NOT_INSTALLED** — wired into `run_all()` but blocked (missing key, timeout, parse error)
- **UNKNOWN** — no `ingest_run` entries and no status information

## DB Schema

### Core Tables

```sql
-- Ingest lifecycle (powops reads via collector_run view)
ingest_run (
  run_id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,          -- ← powops matches on this
  started_at TEXT,
  completed_at TEXT,
  status TEXT,                   -- 'running' | 'ok' | 'error'
  records_seen INTEGER,
  records_accepted INTEGER,
  error_message TEXT
)

-- Content-addressed raw storage
artifact_object (sha256 PK, bytes, content_type, storage_uri, first_seen)
artifact_receipt (id PK, sha256, run_id, source, retrieved_at)

-- Normalized facts (active sources)
price_daily (ticker, date, open, high, low, close, volume, source_id, observed_at)
insider_deals (event_id, ticker, director, position, action, price, shares, value, parse_status, ...)
short_interest (isin, ticker, company, position_pct, notional_gbp, effective_at, ...)
rns_announcements (event_id, ticker, headline, category, effective_at, ...)
company_profiles (ticker, company_number, company_name, status, sic_codes, ...)

-- Legacy
collector_state (source PK, last_run, status, rows, runs)
observation (source, ticker, metric, value, unit, event_time, observed_at)
```

### powops Compatibility View

```sql
CREATE VIEW collector_run AS
SELECT
  run_id,
  source AS source_id,           -- ← powops queries WHERE source_id = ?
  started_at,
  completed_at,
  status,
  error_message AS error,
  CAST((julianday(completed_at) - julianday(started_at)) * 86400 AS INTEGER) AS duration_seconds,
  records_seen AS source_records_new,
  0 AS raw_new
FROM ingest_run;
```

## How powops Reads powstock

### collector_db Check (primary)

```python
# powops/garden.py — read_collector_db()
row = conn.execute(
    "SELECT started_at, status, error, duration_seconds, source_records_new, raw_new "
    "FROM collector_run WHERE source_id = ? ORDER BY run_id DESC LIMIT 1",
    (source_id,)
).fetchone()
```

Status resolution:
- `status == 'error'` → powops shows **error** (does NOT use timestamp as last_success)
- `status == 'ok'` and age < max_staleness → **ok**
- `status == 'ok'` and age > max_staleness → **stale**
- No rows → **unknown**

### Heartbeat Check (fallback)

```json
// data/heartbeat.json — written by run_all()
{
  "heartbeat_at": "2026-09-23T07:02:12.397923",
  "mode": "run_all",
  "total_records": 1372,
  "sources_run": 8,
  "sources_failed": 0,
  "results": { ... }
}
```

## Collector Details

### ACTIVE Collectors

#### yahoo_finance (run_prices)
- **What:** UK equity daily OHLCV prices for 25 universe tickers
- **Source:** Yahoo Finance API (query1.finance.yahoo.com)
- **Table:** `price_daily`
- **Artifacts:** JSON responses stored in objects/
- **Universe:** 25 securities (defined in powstock/universe.py)

#### investegate_rns (run_rns)
- **What:** RNS announcements from Investegate scrape
- **Source:** investegate.co.uk
- **Table:** `rns_announcements`
- **Artifacts:** HTML pages stored in objects/

#### companies_house (run_companies)
- **What:** Company profiles for 25 universe companies
- **Source:** Companies House API (api.company-information.service.gov.uk)
- **Table:** `company_profiles`
- **Requires:** `POWSTOCK_COMPANIES_HOUSE_API_KEY`

#### investegate_pdmr (run_insiders)
- **What:** Director/PDMR insider dealing notifications
- **Source:** Investegate RNS feed
- **Table:** `insider_deals`
- **Artifacts:** HTML notification pages

#### fca_ansp (run_short_interest)
- **What:** FCA short interest positions
- **Source:** FCA ANSP (data.fca.org.uk)
- **Table:** `short_interest`

#### takeover_panel (run_takeover_panel)
- **What:** Takeover Panel disclosure notices
- **Source:** TheTakeoverPanel.org
- **No dedicated table** — writes to `collector_state` only

#### fca_tr1 (run_tr1)
- **What:** FCA TR-1 major shareholder notifications
- **Source:** FCA
- **No dedicated table** — writes to `collector_state` only

#### commodity_prices (run_commodity_prices)
- **What:** Commodity spot prices (oil, gas, metals)
- **Source:** Yahoo Finance
- **No dedicated table** — writes to `collector_state` only

### INACTIVE Collectors (no ingest_run entries)

These are wired into `run_all()` but fail silently (caught by try/except):

| Collector | Likely Failure | Fix |
|---|---|---|
| `finnhub` | Missing `FINNHUB_API_KEY` | Set env var |
| `uk_parliament` | Timeout / network | Increase timeout |
| `congress_trades` | Timeout / network | Increase timeout |
| `european_insiders` | API URL change (returns HTML) | Fix parser |
| `dmo_gilts` | Cloudflare captcha | Add retry/captcha handling |
| `companies_house_psc` | Missing API key or timeout | Set key, increase timeout |
| `ch_company_snapshot` | Download timeout | Increase timeout |
| `ch_accounts_bulk` | Download timeout | Increase timeout |
| `companies_house_filings` | Missing API key | Set `POWSTOCK_COMPANIES_HOUSE_API_KEY` |
| `fca_nsm` | Parse error | Fix HTML parser |

## Running the Pipeline

```bash
cd /root/powstock

# Full pipeline
python3 -c "from powstock.collectors.runner import run_all; run_all()"

# Single collector
python3 -c "from powstock.collectors.runner import run_prices; from powstock.collectors.runner import init_db; conn = init_db(); run_prices(conn)"

# Check status
python3 -c "from powstock.collectors.runner import status; status()"

# powops check
cd /root/powops && python3 -m powops status
```

## Troubleshooting

### Source shows "unknown" in powops
1. Check if collector has ever run: `SELECT * FROM ingest_run WHERE source = '<source_id>'`
2. Run the collector manually and check for errors
3. Verify source_id matches exactly (case-sensitive)

### Source shows "stale" in powops
1. Data is older than `max_staleness` in sources.yaml
2. Run `python3 -c "from powstock.collectors.runner import run_all; run_all()"` to refresh
3. Check if the collector is failing silently (look at try/except output)

### Source shows "error" in powops
1. Check `error_message` in `ingest_run` table
2. Common: missing API key, network timeout, parse error
3. Fix the issue and re-run

### Heartbeat is stale
1. `data/heartbeat.json` is written at end of `run_all()`
2. If stale, the pipeline hasn't run recently
3. Set up a cron job: `*/15 * * * * cd /root/powstock && python3 -c "from powstock.collectors.runner import run_all; run_all()"`
