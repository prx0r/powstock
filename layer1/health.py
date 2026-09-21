"""Layer 1 source health check.

Every collector exposes the same health state.
This is the operational contract for the garden.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SourceHealth:
    """Standardized health state for every source."""
    source_id: str
    last_attempt: str | None = None
    last_success: str | None = None
    records_seen: int = 0
    records_new: int = 0
    bytes: int = 0
    source_timestamp: str | None = None
    schema_hash: str = ""
    status: str = "never_run"  # never_run, ok, stale, error, partial
    error: str | None = None
    consecutive_errors: int = 0

    def is_healthy(self, max_staleness_hours: int = 48) -> bool:
        if self.status == "never_run":
            return False
        if self.status == "error":
            return False
        if self.last_success is None:
            return False
        try:
            last = datetime.fromisoformat(self.last_success)
            age_hours = (datetime.now() - last).total_seconds() / 3600
            return age_hours < max_staleness_hours
        except Exception:
            return False


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
    """Check health of a single source against its manifest."""
    health = SourceHealth(source_id=manifest.id)

    db = Path(db_path)
    if not db.exists():
        health.status = "never_run"
        return health

    conn = sqlite3.connect(str(db))

    # Check collector_state for this source
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

    # Check ingest_run for more detailed info
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

    # Determine status
    if health.last_success:
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
    """Print a formatted health report."""
    print(f"\n{'SOURCE':<25} {'STATUS':<10} {'LAST SUCCESS':<22} {'RECORDS':>8} {'STALE?':<10}")
    print("-" * 85)

    for source_id, h in sorted(health.items()):
        stale = ""
        if h.last_success:
            try:
                last = datetime.fromisoformat(h.last_success)
                age_h = (datetime.now() - last).total_seconds() / 3600
                stale = f"{age_h:.0f}h ago"
            except Exception:
                pass

        print(f"{source_id:<25} {h.status:<10} {(h.last_success or 'never'):<22} {h.records_seen:>8} {stale:<10}")

    print()
