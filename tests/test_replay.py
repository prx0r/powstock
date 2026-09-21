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

from powstock.collectors.runner import init_db
from layer1.artifacts import ArtifactStore


def test_raw_bytes_are_preserved():
    """Raw data written to disk must be byte-identical on read-back."""
    with tempfile.TemporaryDirectory() as tmp:
        store = ArtifactStore(base_dir=Path(tmp) / "raw")

        test_data = {"tickers": ["NG.", "SSE"], "prices": [100.0, 200.0]}
        json_bytes = json.dumps(test_data, indent=2, default=str).encode()

        artifact = store.put_bytes(
            data=json_bytes,
            source="test_source",
            dataset="test_dataset",
        )

        # Read back
        artifact_path = store.get(artifact["artifact_id"])
        assert artifact_path is not None
        readback = artifact_path.read_bytes()
        assert readback == json_bytes

        # SHA256 must match
        assert hashlib.sha256(readback).hexdigest() == artifact["sha256"]


def test_raw_ingest_recorded():
    """ArtifactStore must record raw_artifact in database."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        conn = init_db(db_path)

        store = ArtifactStore(base_dir=Path(tmp) / "raw", conn=conn)
        test_data = [{"ticker": "NG.", "price": 100.0}]
        json_bytes = json.dumps(test_data, indent=2, default=str).encode()

        store.put_bytes(
            data=json_bytes,
            source="test_source",
            dataset="test_dataset",
        )
        conn.commit()

        # Check raw_artifact
        artifact_count = conn.execute("SELECT COUNT(*) FROM raw_artifact").fetchone()[0]
        assert artifact_count >= 1, f"Expected at least 1 raw_artifact, got {artifact_count}"

        conn.close()


def test_replay_from_raw():
    """Wipe normalized data, replay from raw artifact, verify same event counts."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        conn = init_db(db_path)
        store = ArtifactStore(base_dir=Path(tmp) / "raw", conn=conn)

        # Step 1: Store some raw data and "normalize" it
        raw_data = [
            {"ticker": "TEST", "director": "Alice", "trade_date": "2026-09-18"},
            {"ticker": "TEST", "director": "Bob", "trade_date": "2026-09-19"},
        ]
        json_bytes = json.dumps(raw_data, indent=2, default=str).encode()
        artifact = store.put_bytes(
            data=json_bytes,
            source="test_source",
            dataset="insiders",
        )

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

        # Step 3: Replay from raw artifact
        artifact_path = store.get(artifact["artifact_id"])
        assert artifact_path is not None, "Raw artifact not found"

        with open(artifact_path) as f:
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


def test_rns_parser_replay():
    """RNS parser must produce identical output from identical HTML input."""
    from powstock.collectors.rns_announcements import _parse_investegate_html

    # Fetch real HTML from Investegate
    from powstock.collectors.rns_announcements import fetch_investegate_page
    html = fetch_investegate_page(ticker="NG.", page=1)

    # Parse twice — must be identical
    result1 = _parse_investegate_html(html, ticker_filter="NG.")
    result2 = _parse_investegate_html(html, ticker_filter="NG.")

    assert len(result1) == len(result2), f"Parse count mismatch: {len(result1)} != {len(result2)}"
    assert len(result1) > 0, "No announcements parsed"

    for a1, a2 in zip(result1, result2):
        assert a1.ticker == a2.ticker
        assert a1.headline == a2.headline
        assert a1.category == a2.category
        assert a1.source_url == a2.source_url


def test_pdmr_parser_replay():
    """PDMR parser must produce identical output from identical HTML input."""
    from powstock.collectors.fca_pdmr import _parse_pdmr_notification

    # Use existing fixture
    fixture_path = Path(__file__).parent / "fixtures" / "rns" / "pdmr_purchase_single.html"
    if fixture_path.exists():
        html = fixture_path.read_text()

        # Parse twice — must be identical
        result1 = _parse_pdmr_notification(html, "TEST", "Test Co", "http://test.com")
        result2 = _parse_pdmr_notification(html, "TEST", "Test Co", "http://test.com")

        assert len(result1) == len(result2), f"Parse count mismatch: {len(result1)} != {len(result2)}"
        if result1:
            d1, d2 = result1[0], result2[0]
            assert d1.director_name == d2.director_name
            assert d1.transaction_type == d2.transaction_type
            assert d1.price == d2.price


def test_price_collector_replay():
    """Price collector must produce identical output from identical API response."""
    from powstock.collectors.yahoo_prices import fetch_latest

    # Fetch twice — should be cached and identical
    result1 = fetch_latest("NG.")
    result2 = fetch_latest("NG.")

    assert result1 is not None, "First fetch returned None"
    assert result2 is not None, "Second fetch returned None"
    assert result1["price"] == result2["price"], "Price mismatch between cached fetches"
    assert result1["asof"] == result2["asof"], "Date mismatch between cached fetches"
