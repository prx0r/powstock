# Collectors

Every data source has a collector module in `powstock/collectors/`. Collectors fetch raw bytes, store them via ArtifactStore, and parse into normalized facts.

## Collector Inventory

### Active (run by `make run`)

| Module | Source | Data | Status |
|--------|--------|------|--------|
| `yahoo_prices.py` | Yahoo Finance | Daily OHLCV | ✅ 24/25 tickers |
| `fca_pdmr.py` | Investegate | Insider dealing | ⚠️ Non-universe stocks |
| `fca_short_interest.py` | FCA ANSP | Short positions | ✅ 421 positions |
| `rns_announcements.py` | Investegate | RNS announcements | ✅ 891 announcements |
| `companies_house.py` | Companies House | Company profiles | ✅ 25/25 tickers |
| `finnhub.py` | Finnhub | SEC insider txns | 🔑 Needs API key |

### Registered (in `layer1/registry.py`, not wired to `run_all()`)

| Module | Source | Data | Status |
|--------|--------|------|--------|
| `tracefour.py` | Tracefour | UK PDMR, clusters, streaks | 🔑 Needs API key |
| `psc_snapshot.py` | Companies House | PSC daily bulk | ✅ Built |
| `fca_nsm.py` | FCA | Regulatory announcements | ✅ Built |
| `takeover_panel.py` | Takeover Panel | Disclosure forms | ✅ Built |
| `tr1_notifications.py` | FCA | Major shareholder changes | ✅ Built |
| `filing_events.py` | Companies House | Filing → economic events | ✅ Built |
| `ch_company_snapshot.py` | Companies House | Full UK company population | ✅ Built |
| `ch_accounts_bulk.py` | Companies House | XBRL accounts bulk | ✅ Built |
| `stooq_prices.py` | Stooq | Daily OHLCV | ⏸️ Disabled (Yahoo primary) |

### Dead (never imported, never used)

| Module | Why Dead |
|--------|----------|
| `financials.py` | Missing `stream-read-xbrl` dependency |
| `ch_bulk_parsers.py` | Never registered, never tested |

## Collector Pattern

Every collector follows the same contract:

```python
def fetch_source_data(...) -> tuple[list[dict], bytes]:
    """Fetch from source. Returns (parsed_facts, raw_bytes)."""

def parse_source(raw_bytes: bytes) -> list[dict]:
    """Parse raw bytes into normalized facts."""
```

The runner orchestrates:

```python
with IngestRun(conn, source="source_id") as run:
    facts, raw_bytes = fetch_source_data()
    artifact = store.put_http_response(raw_bytes, run_id=run.id)
    for fact in facts:
        conn.execute("INSERT OR REPLACE INTO ...", fact)
    run.complete(records_seen=len(facts))
```

## Adding a New Collector

1. Create `powstock/collectors/new_source.py`
2. Implement `fetch_source_data()` and `parse_source()`
3. Register in `layer1/registry.py`:
   ```python
   register(source_id="new_source", name="New Source", enabled=True,
            module="powstock.collectors.new_source", function="fetch_source_data")
   ```
4. Add a source manifest in `layer1/sources/new_source/manifest.yaml`
5. Add a `run_new_source()` function in `runner.py`
6. Wire into `run_all()`
