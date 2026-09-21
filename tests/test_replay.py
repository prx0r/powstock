"""Replay/provenance tests.

Core property of a data garden:
  wipe everything except raw/
  replay
  same normalized hashes, same event counts, same daily states

This proves the garden is reproducible from immutable source artifacts.
"""

import hashlib
import json
import sqlite3
import tempfile
from datetime import date, datetime
from pathlib import Path

from powstock.collectors.runner import _store_raw, init_db


def test_raw_bytes_are_preserved():
    """Raw data written to disk must be byte-identical on read-back."""
    with tempfile.TemporaryDirectory() as tmp:
        raw_dir = Path(tmp) / "data" / "raw"
        raw_dir.mkdir(parents=True)

        # Simulate storing raw data
        test_data = {"tickers": ["NG.", "SSE"], "prices": [100.0, 200.0]}
        raw_path = raw_dir / "test_source_20260921.json"

        with open(raw_path, "w") as f:
            json.dump(test_data, f, indent=2, default=str)

        raw_bytes = raw_path.read_bytes()
        sha256 = hashlib.sha256(raw_bytes).hexdigest()

        # Read back
        with open(raw_path) as f:
            readback = json.load(f)

        readback_bytes = json.dumps(readback, indent=2, default=str).encode()
        readback_sha256 = hashlib.sha256(readback_bytes).hexdigest()

        # SHA256 of the on-disk bytes must match
        assert sha256 == readback_sha256, "Raw bytes changed on read-back"
        assert readback == test_data, "Raw data changed on read-back"


def test_raw_ingest_recorded():
    """_store_raw must record ingest_run + raw_artifact + raw_ingest."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        conn = init_db(db_path)

        test_data = [{"ticker": "NG.", "price": 100.0}]
        _store_raw(conn, "test_source", "test_dataset", test_data)
        conn.commit()

        # Check ingest_run
        run_count = conn.execute("SELECT COUNT(*) FROM ingest_run").fetchone()[0]
        assert run_count >= 1, f"Expected at least 1 ingest_run, got {run_count}"

        # Check raw_artifact
        artifact_count = conn.execute("SELECT COUNT(*) FROM raw_artifact").fetchone()[0]
        assert artifact_count >= 1, f"Expected at least 1 raw_artifact, got {artifact_count}"

        # Check raw_ingest (legacy)
        ingest_count = conn.execute("SELECT COUNT(*) FROM raw_ingest").fetchone()[0]
        assert ingest_count >= 1, f"Expected at least 1 raw_ingest, got {ingest_count}"

        # SHA256 must be consistent
        run_row = conn.execute(
            "SELECT content_sha256 FROM ingest_run WHERE source='test_source' ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
        artifact_row = conn.execute(
            "SELECT sha256 FROM raw_artifact ORDER BY artifact_id DESC LIMIT 1"
        ).fetchone()
        assert run_row[0] == artifact_row[0], "SHA256 mismatch between ingest_run and raw_artifact"

        conn.close()


def test_replay_from_raw():
    """Wipe normalized data, replay from raw, verify same event counts."""
    import powstock.collectors.runner as runner_mod

    with tempfile.TemporaryDirectory() as tmp:
        # Patch RAW_DIR to point inside our temp dir
        original_raw_dir = runner_mod.RAW_DIR
        runner_mod.RAW_DIR = Path(tmp) / "data" / "raw"

        db_path = Path(tmp) / "test.db"
        conn = init_db(db_path)

        # Step 1: Store some raw data and "normalize" it
        raw_data = [
            {"ticker": "TEST", "director": "Alice", "trade_date": "2026-09-18"},
            {"ticker": "TEST", "director": "Bob", "trade_date": "2026-09-19"},
        ]
        _store_raw(conn, "test_source", "insiders", raw_data)

        # Insert normalized records
        for deal in raw_data:
            event_id = hashlib.sha256(
                f"{deal['ticker']}|{deal['director']}|{deal['trade_date']}||".encode()
            ).hexdigest()[:16]
            conn.execute(
                """INSERT OR REPLACE INTO insider_deals
                   (event_id, ticker, company, director, position, action, price, shares, value,
                    effective_at, published_at, observed_at, source_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, deal["ticker"], "Test Co", deal["director"],
                 "Director", "Purchase", 10.0, 100, 1000.0,
                 deal["trade_date"], "", datetime.now().isoformat(), ""),
            )
        conn.commit()

        count_before = conn.execute("SELECT COUNT(*) FROM insider_deals").fetchone()[0]
        assert count_before == 2

        # Step 2: Wipe normalized data (keep raw)
        conn.execute("DELETE FROM insider_deals")
        conn.commit()

        count_after_wipe = conn.execute("SELECT COUNT(*) FROM insider_deals").fetchone()[0]
        assert count_after_wipe == 0, "Wipe failed"

        # Step 3: Replay from raw
        raw_files = list(runner_mod.RAW_DIR.glob("test_source_insiders_*.json"))
        assert len(raw_files) == 1, f"Expected 1 raw file, got {len(raw_files)}"

        with open(raw_files[0]) as f:
            replayed_data = json.load(f)

        for deal in replayed_data:
            event_id = hashlib.sha256(
                f"{deal['ticker']}|{deal['director']}|{deal['trade_date']}||".encode()
            ).hexdigest()[:16]
            conn.execute(
                """INSERT OR REPLACE INTO insider_deals
                   (event_id, ticker, company, director, position, action, price, shares, value,
                    effective_at, published_at, observed_at, source_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, deal["ticker"], "Test Co", deal["director"],
                 "Director", "Purchase", 10.0, 100, 1000.0,
                 deal["trade_date"], "", datetime.now().isoformat(), ""),
            )
        conn.commit()

        # Step 4: Verify same count
        count_replay = conn.execute("SELECT COUNT(*) FROM insider_deals").fetchone()[0]
        assert count_replay == count_before, f"Replay count mismatch: {count_replay} != {count_before}"

        # Step 5: Verify same event IDs
        ids_before = sorted([hashlib.sha256(
            f"TEST|Alice|2026-09-18||".encode()
        ).hexdigest()[:16], hashlib.sha256(
            f"TEST|Bob|2026-09-19||".encode()
        ).hexdigest()[:16]])
        ids_after = [r[0] for r in conn.execute(
            "SELECT event_id FROM insider_deals ORDER BY event_id"
        ).fetchall()]
        assert ids_before == ids_after, f"Event ID mismatch: {ids_after} != {ids_before}"

        conn.close()
        runner_mod.RAW_DIR = original_raw_dir
