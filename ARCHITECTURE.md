# Architecture

powstock is a data garden. Layer 1 collects and archives. Layer 2 analyzes. They are independent.

## Design Principles

1. **Raw bytes before parsing** — every collector stores original source bytes via ArtifactStore before any normalization
2. **Content-addressed** — same bytes = same SHA256 = stored once globally
3. **Provenance on every fact** — every normalized row references source_id, artifact_id, parser_version
4. **Layer independence** — Layer 1 works without powk, signals, fish, or any Layer 2/3 system
5. **Null means unknown** — missing data is NULL, never zero or false

## System Layout

```
powstock/
├── powstock/              ← Core package
│   ├── universe.py        ← 25 securities (hard-coded CH number, ISIN, LEI)
│   ├── settings.py        ← pydantic-settings, reads .env
│   ├── collectors/        ← 20 collector modules
│   └── schema/            ← Daily state dataclass + builder
│
├── layer1/                ← Data Garden (no Layer 2 dependencies)
│   ├── artifacts.py       ← ArtifactStore + IngestRun
│   ├── registry.py        ← Collector registry
│   ├── health.py          ← 3-level health monitoring
│   └── sources/           ← 16 source manifests
│
├── layer2/                ← Analysis (consumes Layer 1)
│   ├── signals/           ← 10 signal functions
│   ├── bridge.py          ← powk canonical export
│   └── experiments/       ← Empty (Layer 1 must be complete first)
│
├── scripts/               ← Pipeline scripts
├── tests/                 ← 21 tests
└── data/                  ← Database + object store
```

## Storage Model

### Objects (global, content-addressed)

```
data/raw/objects/{ab}/{cd}/{sha256}.bin
```

- Same bytes stored once globally
- SHA256 is the primary key
- Sidecar `.meta.json` for disaster recovery
- Canonical index is SQLite, not filesystem

### Receipts (per-run observations)

One object can have many receipts:

```
sha256 = XYZ

receipts:
  2026-09-20 08:03  run_id=42  source=yahoo_finance
  2026-09-21 08:02  run_id=43  source=yahoo_finance
  2026-09-22 08:04  run_id=44  source=yahoo_finance
```

Deduplicate the bytes, not the observation.

### Ingest Runs (lifecycle tracking)

```python
with IngestRun(conn, source="yahoo_finance") as run:
    artifact = store.put_http_response(..., run_id=run.id)
    facts = parse(artifact)
    run.complete(records_seen=len(facts))
```

Every collection attempt is a bounded run with start/end, status, error capture, and artifact linkage.

## Data Flow

```
REALITY (LSE, FCA, Companies House, Investegate, Yahoo)
  ↓
COLLECTORS (fetch raw bytes via httpx)
  ↓
ARTIFACT STORE (SHA256 content-addressed, global dedup)
  ↓
INGEST RUN (lifecycle: start → fetch → store → parse → complete)
  ↓
NORMALIZED FACTS (every fact has source_id, artifact_id, parser_version)
  ↓
DAILY STATE (one snapshot per security per day)
  ↓
SIGNALS (cross-source, z-scored, versioned)
  ↓
EXPERIMENTS (hypothesis → evaluation with frozen provenance)
```

## Collector Contract

Every enabled collector must:

1. **Fetch raw bytes** from the source
2. **Store via ArtifactStore** before parsing
3. **Parse** the raw bytes into normalized facts
4. **Record** facts with provenance (source_id, artifact_id, parser_version)

No collector may bypass raw storage. The registry drives execution.

## Dependency Model

```
Layer 1 deps:  httpx, pydantic, pydantic-settings, pyyaml
Layer 2 deps:  powkernel (optional), numpy, pandas
```

Layer 1 cannot break because Layer 2 changes. `pip install powstock` installs Layer 1 only. `pip install powstock[k3]` adds powk for Layer 2 bridge.

## Database Schema (v2)

### Ingest Lifecycle
```sql
ingest_run (
  run_id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,
  dataset TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT DEFAULT 'running',
  parser_version TEXT,
  records_seen INTEGER,
  records_accepted INTEGER,
  records_rejected INTEGER,
  error_message TEXT
)
```

### Content-Addressed Storage
```sql
artifact_object (
  sha256 TEXT PRIMARY KEY,
  bytes INTEGER NOT NULL,
  content_type TEXT,
  storage_uri TEXT NOT NULL,
  first_seen TEXT NOT NULL
)

artifact_receipt (
  id INTEGER PRIMARY KEY,
  sha256 TEXT REFERENCES artifact_object(sha256),
  run_id INTEGER REFERENCES ingest_run(run_id),
  source TEXT NOT NULL,
  retrieved_at TEXT NOT NULL
)
```

### Normalized Facts
```sql
price_daily (..., source_id, artifact_id, parser_version, observed_at)
insider_deals (..., source_id, artifact_id, parser_version, observed_at)
short_interest (..., source_id, artifact_id, parser_version, observed_at)
rns_announcements (..., source_id, artifact_id, parser_version, observed_at)
company_profiles (..., source_id, artifact_id, parser_version, observed_at)
```

### Coverage Tracking
```sql
source_coverage (
  source_id TEXT PRIMARY KEY,
  coverage_start TEXT,
  coverage_end TEXT,
  continuity_pct REAL,
  last_checked_at TEXT
)
```

## What powstock Does NOT Import

- fish (trading system) — Layer 1 is standalone
- powuk (UK infrastructure) — patterns reused, no code dependency
- powpowpow (crypto garden) — architecture inspired, no code dependency

Layer 1 is a clean, independent data garden. It feeds downstream consumers but depends on none of them.
