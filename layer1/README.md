# Layer 1 — The Data Garden

Layer 1 is the immutable UK corporate/market tape. No signals, no experiments, no trading logic. Just the tape.

**Completion definition:**
> Every enabled source archives original bytes before parsing. Every normalized fact points back to exact artifact bytes and parser version. The complete database can be rebuilt offline from retained raw artifacts.

## Architecture

```
layer1/
├── artifacts.py         ← ArtifactStore + IngestRun
├── registry.py          ← Collector registry (manifest-driven)
├── health.py            ← 3-level health monitoring
├── manifest_schema.yaml ← Source manifest schema
└── sources/             ← 16 source manifests (YAML)
```

## Core Components

### ArtifactStore (`artifacts.py`)

Global content-addressed raw artifact storage.

```python
store = ArtifactStore(base_dir="data/raw", conn=conn)

# Store raw bytes — creates global object + receipt
artifact = store.put_bytes(
    data=response.content,
    source="yahoo_finance",
    dataset="latest_prices",
    run_id=run.id,
)

# Same bytes stored twice → one object, two receipts
# Different runs fetching identical bytes = new receipt, not new object
```

**Object layout:**
```
data/raw/objects/{ab}/{cd}/{sha256}.bin
```

**Database tables:**
- `artifact_object` — canonical index (sha256, bytes, content_type, storage_uri)
- `artifact_receipt` — per-run observations (sha256, run_id, source, retrieved_at)

### IngestRun (`artifacts.py`)

Bounded collection attempt with lifecycle tracking.

```python
with IngestRun(conn, source="yahoo_finance", dataset="latest_prices") as run:
    # run.id is auto-generated
    artifact = store.put_http_response(..., run_id=run.id)
    facts = parse(artifact)
    run.complete(records_seen=len(facts))
    # On exception: status='error', error_message recorded
```

**Lifecycle:** start → fetch → store → parse → complete

**Error handling:**
- IO/network errors → suppressed, recorded in DB
- Programming errors → re-raised after recording

### Collector Registry (`registry.py`)

Manifest-driven collector execution.

```python
from layer1.registry import get_enabled, register

# Register a collector
register(
    source_id="yahoo_prices",
    name="Yahoo Finance Prices",
    enabled=True,
    module="powstock.collectors.yahoo_prices",
    function="fetch_all_latest",
)

# Get all enabled collectors
for entry in get_enabled():
    execute(entry)
```

### Health Monitoring (`health.py`)

Three levels of health per source:

1. **Source Health** — can we reach the source?
2. **Ingest Health** — did we archive today's expected artifact?
3. **Data Health** — does the artifact look plausible?

```bash
make health
```

## Source Manifests

Every source has a YAML manifest in `layer1/sources/{source_id}/manifest.yaml`:

```yaml
id: yahoo_prices
garden: powstock
source:
  authority: Yahoo Finance
  type: json
  url: https://query1.finance.yahoo.com
collection:
  cadence: daily
  backfill_from: "2025-01-01"
  method: http_get
storage:
  raw: true
  append_only: true
health:
  expected_min_rows: 20
  max_staleness_hours: 48
```

## Source Inventory

| Source ID | Authority | Data | Status |
|-----------|-----------|------|--------|
| yahoo_prices | Yahoo Finance | Daily OHLCV | ✅ Active |
| fca_short_interest | FCA | Short positions | ✅ Active |
| investegate_rns | Investegate | RNS announcements | ✅ Active |
| companies_house | Companies House | Company profiles | ✅ Active |
| investegate_pdmr | Investegate | Insider dealing | ⚠️ Non-universe |
| finnhub_insider | Finnhub | SEC insider txns | 🔑 Needs key |
| tracefour | Tracefour | UK PDMR, clusters | 🔑 Needs key |
| psc_snapshot | Companies House | PSC daily bulk | ✅ Built |
| fca_nsm | FCA | Regulatory announcements | ✅ Built |
| takeover_panel | Takeover Panel | Disclosure forms | ✅ Built |
| tr1_notifications | FCA | Major shareholder | ✅ Built |
| filing_events | Companies House | Filing → events | ✅ Built |
| ch_company_snapshot | Companies House | Full UK companies | ✅ Built |
| ch_accounts_bulk | Companies House | XBRL accounts | ✅ Built |

## Schema (v2)

### Ingest Lifecycle
```sql
ingest_run (run_id, source, dataset, started_at, completed_at, status, ...)
```

### Content-Addressed Storage
```sql
artifact_object (sha256, bytes, content_type, storage_uri, first_seen)
artifact_receipt (sha256, run_id, source, dataset, retrieved_at)
```

### Normalized Facts (every fact has provenance)
```sql
price_daily (..., source_id, artifact_id, parser_version, observed_at)
insider_deals (..., source_id, artifact_id, parser_version, observed_at)
short_interest (..., source_id, artifact_id, parser_version, observed_at)
rns_announcements (..., source_id, artifact_id, parser_version, observed_at)
company_profiles (..., source_id, artifact_id, parser_version, observed_at)
```

### Coverage Tracking
```sql
source_coverage (source_id, coverage_start, coverage_end, continuity_pct, ...)
```

## Running

```bash
# Run all collectors
make run

# Run backfill
python scripts/backfill_prices.py --days 365

# Check health
make health

# Run tests
make test
```
