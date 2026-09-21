"""Layer 1 manifest and health tests.

Verifies all source manifests parse correctly and health checks run.
"""

from pathlib import Path

import pytest

from layer1.health import SourceHealth, load_manifest, check_all_health, print_health_report

SOURCES_DIR = Path(__file__).parent.parent / "layer1" / "sources"


def test_all_manifests_parse():
    """Every source directory with a manifest.yaml must parse."""
    manifest_files = sorted(SOURCES_DIR.glob("*/manifest.yaml"))
    assert len(manifest_files) >= 8, f"Expected at least 8 manifests, got {len(manifest_files)}"

    for mf in manifest_files:
        manifest = load_manifest(mf)
        assert manifest.id, f"Manifest {mf} has no id"
        assert manifest.garden == "powstock", f"Manifest {mf} garden != powstock"
        assert manifest.source_authority, f"Manifest {mf} has no source authority"
        assert manifest.collection_cadence, f"Manifest {mf} has no cadence"
        assert manifest.health_max_staleness_hours > 0, f"Manifest {mf} has no staleness threshold"


def test_manifest_schema_fields():
    """Verify manifest schema has required fields."""
    manifest = load_manifest(SOURCES_DIR / "yahoo_prices" / "manifest.yaml")
    assert manifest.id == "yahoo_prices"
    assert manifest.source_authority == "Yahoo Finance"
    assert manifest.collection_cadence == "daily"
    assert manifest.storage_raw is True
    assert manifest.storage_append_only is True
    assert manifest.time_source_timestamp is True
    assert manifest.time_observed_at is True
    assert len(manifest.schema_columns) > 0
    assert len(manifest.schema_unique_keys) > 0


def test_manifest_unique_keys_are_valid():
    """All unique_keys must reference columns in schema."""
    for mf in SOURCES_DIR.glob("*/manifest.yaml"):
        manifest = load_manifest(mf)
        for key in manifest.schema_unique_keys:
            assert key in manifest.schema_columns, (
                f"Manifest {manifest.id}: unique_key '{key}' not in columns {manifest.schema_columns}"
            )


def test_health_check_runs():
    """Health check must run without errors on all manifests."""
    health = check_all_health(base_dir=SOURCES_DIR)
    assert len(health) >= 8
    for source_id, h in health.items():
        assert isinstance(h, SourceHealth)
        assert h.source_id == source_id
        assert h.status in ("never_run", "ok", "stale", "error", "partial")


def test_health_report_prints(capsys):
    """Health report must print without errors."""
    health = check_all_health(base_dir=SOURCES_DIR)
    print_health_report(health)
    captured = capsys.readouterr()
    assert "SOURCE" in captured.out
    assert "STATUS" in captured.out


def test_all_sources_have_health_check():
    """Every manifest must have a corresponding health entry."""
    manifest_ids = set()
    for mf in SOURCES_DIR.glob("*/manifest.yaml"):
        manifest = load_manifest(mf)
        manifest_ids.add(manifest.id)

    health = check_all_health(base_dir=SOURCES_DIR)
    for mid in manifest_ids:
        assert mid in health, f"Source {mid} has manifest but no health entry"
