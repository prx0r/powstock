"""Idempotence tests.

Core property: running a collector twice must not create duplicates.
"""

import sqlite3
from pathlib import Path
from unittest.mock import patch

from powstock.collectors.runner import init_db


def _make_test_db(tmp_path: Path) -> sqlite3.Connection:
    """Create a fresh test database."""
    return init_db(tmp_path / "test.db")


def test_init_db_creates_tables():
    """Verify all expected tables are created."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        conn = _make_test_db(Path(tmp))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {t[0] for t in tables}

        assert "raw_ingest" in table_names
        assert "observation" in table_names
        assert "collector_state" in table_names
        assert "price_daily" in table_names
        assert "insider_deals" in table_names
        assert "short_interest" in table_names
        assert "rns_announcements" in table_names
        assert "company_profiles" in table_names
        assert "ingest_run" in table_names
        assert "raw_artifact" in table_names
        conn.close()


def test_price_upsert_idempotent():
    """Inserting the same price twice must not create duplicates."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        conn = _make_test_db(Path(tmp))

        # Insert same price twice
        for _ in range(2):
            conn.execute(
                "INSERT OR REPLACE INTO price_daily (ticker, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("TEST.L", "2026-09-21", 100.0, 105.0, 99.0, 102.0, 1000),
            )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM price_daily").fetchone()[0]
        assert count == 1, f"Expected 1 row after upsert, got {count}"
        conn.close()


def test_insider_upsert_idempotent():
    """Inserting the same insider deal twice must not create duplicates."""
    import hashlib
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        conn = _make_test_db(Path(tmp))

        event_id = hashlib.sha256(b"TEST|John Smith|2026-09-18|Purchase|http://test.com").hexdigest()[:16]

        for _ in range(2):
            conn.execute(
                """INSERT OR REPLACE INTO insider_deals
                   (event_id, ticker, company, director, position, action, price, shares, value,
                    effective_at, published_at, observed_at, source_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, "TEST", "Test Co", "John Smith", "CEO", "Purchase",
                 10.0, 100, 1000.0, "2026-09-18", "2026-09-19",
                 "2026-09-20T07:00:00", "http://test.com"),
            )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM insider_deals").fetchone()[0]
        assert count == 1, f"Expected 1 row after upsert, got {count}"
        conn.close()


def test_rns_upsert_idempotent():
    """Inserting the same RNS announcement twice must not create duplicates."""
    import hashlib
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        conn = _make_test_db(Path(tmp))

        event_id = hashlib.sha256(b"TEST|http://investegate.co.uk/test-001").hexdigest()[:16]

        for _ in range(2):
            conn.execute(
                """INSERT OR REPLACE INTO rns_announcements
                   (event_id, ticker, headline, category, effective_at, published_at,
                    observed_at, source_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, "TEST", "Test Announcement", "RNS",
                 "2026-09-21", "2026-09-21T07:00:00",
                 "2026-09-21T07:01:00", "http://investegate.co.uk/test-001"),
            )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM rns_announcements").fetchone()[0]
        assert count == 1, f"Expected 1 row after upsert, got {count}"
        conn.close()
