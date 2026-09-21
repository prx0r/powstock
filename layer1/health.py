"""Layer 1 health — three levels of health monitoring.

Every source must answer:
1. SOURCE HEALTH — can we reach the source?
2. INGEST HEALTH — did we archive today's expected artifact?
3. DATA HEALTH — does today's artifact resemble a plausible dataset?

This is where manifests become genuinely powerful.

Status: STALE
- Never imported by any module.
- Only reachable via Makefile `make health` target.
- Requires source manifests in layer1/sources/*/manifest.yaml (14 exist).
- Would be useful for operational monitoring once pipeline is running daily.
- To use: make health or python -c "from layer1.health import check_all_health, print_health_report; print_health_report(check_all_health())"
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SourceHealth:
    """Three-level health state for every source."""
    source_id: str

    # Level 1: Source Health — can we reach the source?
    source_reachable: bool | None = None  # None = unknown
    source_last_reachability_check: str | None = None
    source_error: str | None = None

    # Level 2: Ingest Health — did we archive today's artifact?
    last_attempt: str | None = None
    last_success: str | None = None
    records_seen: int = 0
    records_new: int = 0
    bytes: int = 0
    artifact_count: int = 0
    source_timestamp: str | None = None
    consecutive_errors: int = 0

    # Level 3: Data Health — does the artifact look plausible?
    schema_hash: str = ""
    expected_min_rows: int = 0
    actual_rows: int = 0
    data_plausible: bool | None = None  # None = not checked
    schema_drift: str | None = None  # None = no drift, string = description

    # Overall
    status: str = "never_run"  # never_run, ok, stale, error, partial, source_down
    error: str | None = None

    def is_healthy(self, max_staleness_hours: int = 48) -> bool:
        if self.status in ("never_run", "error", "source_down"):
            return False
        if self.last_success is None:
            return False
        try:
            last = datetime.fromisoformat(self.last_success)
            age_hours = (datetime.now() - last).total_seconds() / 3600
            return age_hours < max_staleness_hours
        except Exception:
            return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for reporting."""
        return {
            "source_id": self.source_id,
            "status": self.status,
            "source_reachable": self.source_reachable,
            "last_success": self.last_success,
            "records_seen": self.records_seen,
            "bytes": self.bytes,
            "artifact_count": self.artifact_count,
            "data_plausible": self.data_plausible,
            "schema_drift": self.schema_drift,
            "error": self.error,
        }


@dataclass
class SourceManifest:
    """Parsed source manifest."""
    id: str
    garden: str
    source_authority: str
    source_type: str
    source_url: str
    license: str
    collection_cadence: str
    collection_backfill_from: str
    collection_method: str
    collection_rate_limit: str
    collection_parser: str
    storage_raw: bool
    storage_append_only: bool
    storage_format: str
    time_source_timestamp: bool
    time_observed_at: bool
    time_effective_field: str
    time_published_field: str
    health_expected_min_rows: int
    health_max_staleness_hours: int
    health_schema_hash: str
    health_error_threshold: int
    schema_columns: list[str] = field(default_factory=list)
    schema_unique_keys: list[str] = field(default_factory=list)
    schema_event_id_fields: list[str] = field(default_factory=list)
    # History/backfill metadata
    history_mode: str = "forward_only"  # backfill | partial | forward_only
    history_earliest_available: str = ""
    history_backfill_status: str = ""
    history_continuity_checked: bool = False


def load_manifest(path: str | Path) -> SourceManifest:
    """Load a YAML source manifest."""
    with open(path) as f:
        data = yaml.safe_load(f)

    src = data.get("source", {})
    coll = data.get("collection", {})
    stor = data.get("storage", {})
    tm = data.get("time", {})
    hlth = data.get("health", {})
    sch = data.get("schema", {})
    hist = data.get("history", {})

    return SourceManifest(
        id=data["id"],
        garden=data["garden"],
        source_authority=src.get("authority", ""),
        source_type=src.get("type", ""),
        source_url=src.get("url", ""),
        license=src.get("license", ""),
        collection_cadence=coll.get("cadence", ""),
        collection_backfill_from=coll.get("backfill_from", ""),
        collection_method=coll.get("method", ""),
        collection_rate_limit=coll.get("rate_limit", ""),
        collection_parser=coll.get("parser", ""),
        storage_raw=stor.get("raw", True),
        storage_append_only=stor.get("append_only", True),
        storage_format=stor.get("format", "jsonl"),
        time_source_timestamp=tm.get("source_timestamp", True),
        time_observed_at=tm.get("observed_at", True),
        time_effective_field=tm.get("effective_field", ""),
        time_published_field=tm.get("published_field", ""),
        health_expected_min_rows=hlth.get("expected_min_rows", 0),
        health_max_staleness_hours=hlth.get("max_staleness_hours", 48),
        health_schema_hash=hlth.get("schema_hash", ""),
        health_error_threshold=hlth.get("error_threshold", 3),
        schema_columns=sch.get("columns", []),
        schema_unique_keys=sch.get("unique_keys", []),
        schema_event_id_fields=sch.get("event_id_fields", []),
        history_mode=hist.get("mode", "forward_only"),
        history_earliest_available=hist.get("earliest_available", ""),
        history_backfill_status=hist.get("backfill_status", ""),
        history_continuity_checked=hist.get("continuity_checked", False),
    )


def check_all_health(
    base_dir: str | Path = "layer1/sources",
    db_path: str | Path = "data/powstock.db",
) -> dict[str, SourceHealth]:
    """Check health of all sources with manifests."""
    base = Path(base_dir)
    results: dict[str, SourceHealth] = {}

    for manifest_path in sorted(base.glob("*/manifest.yaml")):
        try:
            manifest = load_manifest(manifest_path)
            health = _check_source_health(manifest, db_path)
            results[manifest.id] = health
        except Exception as e:
            source_id = manifest_path.parent.name
            results[source_id] = SourceHealth(
                source_id=source_id,
                status="error",
                error=str(e),
            )

    return results


def _check_source_health(manifest: SourceManifest, db_path: str | Path) -> SourceHealth:
    """Check health of a single source against its manifest.

    Three levels:
    1. Source Health — can we reach the source?
    2. Ingest Health — did we archive today's artifact?
    3. Data Health — does the artifact look plausible?
    """
    health = SourceHealth(source_id=manifest.id)

    db = Path(db_path)
    if not db.exists():
        health.status = "never_run"
        return health

    conn = sqlite3.connect(str(db))

    # Level 1: Source Health — check reachability
    try:
        # Try to reach the source URL (lightweight check)
        import httpx
        client = httpx.Client(timeout=10, follow_redirects=True)
        try:
            resp = client.head(manifest.source_url)
            health.source_reachable = resp.status_code < 500
            health.source_last_reachability_check = datetime.now().isoformat()
        except Exception as e:
            health.source_reachable = False
            health.source_error = str(e)
        finally:
            client.close()
    except ImportError:
        health.source_reachable = None  # can't check without httpx

    # Level 2: Ingest Health — check collector_state
    try:
        row = conn.execute(
            "SELECT last_run, status, rows, runs FROM collector_state WHERE source=?",
            (manifest.id,),
        ).fetchone()
        if row:
            health.last_attempt = row[0]
            health.records_seen = row[2] or 0
            if row[1] == "ok":
                health.last_success = row[0]
    except Exception:
        pass

    # Check ingest_run for more detail
    try:
        row = conn.execute(
            """SELECT completed_at, records_seen, records_accepted, content_length, content_sha256
               FROM ingest_run WHERE source=? ORDER BY run_id DESC LIMIT 1""",
            (manifest.id,),
        ).fetchone()
        if row:
            health.last_success = row[0]
            health.records_seen = row[1] or 0
            health.records_new = row[2] or 0
            health.bytes = row[3] or 0
            health.schema_hash = row[4] or ""
    except Exception:
        pass

    # Count raw artifacts
    try:
        count = conn.execute(
            """SELECT COUNT(*) FROM artifact_receipt WHERE source = ?""",
            (manifest.id,),
        ).fetchone()[0]
        health.artifact_count = count
    except Exception:
        pass

    # Level 3: Data Health — check plausibility
    health.expected_min_rows = manifest.health_expected_min_rows
    health.actual_rows = health.records_seen

    if health.records_seen > 0 and manifest.health_expected_min_rows > 0:
        health.data_plausible = health.records_seen >= manifest.health_expected_min_rows * 0.1
    elif health.records_seen > 0:
        health.data_plausible = True
    else:
        health.data_plausible = None  # no data to check

    # Determine overall status
    if health.source_reachable is False:
        health.status = "source_down"
    elif health.last_success:
        try:
            last = datetime.fromisoformat(health.last_success)
            age_hours = (datetime.now() - last).total_seconds() / 3600
            if age_hours > manifest.health_max_staleness_hours:
                health.status = "stale"
            elif health.records_seen < manifest.health_expected_min_rows:
                health.status = "partial"
            else:
                health.status = "ok"
        except Exception:
            health.status = "ok"
    elif health.last_attempt:
        health.status = "error"
    else:
        health.status = "never_run"

    conn.close()
    return health


def print_health_report(health: dict[str, SourceHealth]) -> None:
    """Print a formatted health report with three levels."""
    print(f"\n{'SOURCE':<25} {'STATUS':<12} {'REACH':<8} {'RECORDS':>8} {'ARTIFACTS':>9} {'DATA?':<8} {'STALE?':<10}")
    print("-" * 95)

    for source_id, h in sorted(health.items()):
        reach = "✓" if h.source_reachable else ("✗" if h.source_reachable is False else "?")
        plausible = "✓" if h.data_plausible else ("✗" if h.data_plausible is False else "?")
        stale = ""
        if h.last_success:
            try:
                last = datetime.fromisoformat(h.last_success)
                age_h = (datetime.now() - last).total_seconds() / 3600
                stale = f"{age_h:.0f}h ago"
            except Exception:
                pass

        print(f"{source_id:<25} {h.status:<12} {reach:<8} {h.records_seen:>8} {h.artifact_count:>9} {plausible:<8} {stale:<10}")

    print()
