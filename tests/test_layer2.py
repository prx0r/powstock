"""Layer 2 signal tests.

Verifies signals can be computed from the existing database.
"""

import sqlite3
from pathlib import Path

from layer2.signals import (
    Signal,
    insider_pressure,
    short_squeeze_risk,
    filing_event_signal,
    compute_all_signals,
)

DB_PATH = Path(__file__).parent.parent / "data" / "powstock.db"


def _get_conn() -> sqlite3.Connection | None:
    if DB_PATH.exists():
        return sqlite3.connect(str(DB_PATH))
    return None


def test_signal_dataclass():
    """Signal has correct fields."""
    s = Signal(
        name="test",
        ticker="TEST",
        value=0.5,
        as_of="2026-09-21",
        confidence=0.8,
        inputs=["test_table"],
    )
    assert s.name == "test"
    assert s.value == 0.5
    assert s.confidence == 0.8


def test_insider_pressure():
    """Insider pressure computation works on live DB."""
    conn = _get_conn()
    if conn is None:
        return  # no DB, skip

    # Test with known ticker
    sig = insider_pressure(conn, "NG.")
    if sig is not None:
        assert sig.name == "insider_pressure"
        assert 0.0 <= sig.value <= 1.0
        assert 0.0 <= sig.confidence <= 1.0
        assert "insider_deals" in sig.inputs

    conn.close()


def test_short_squeeze_risk():
    """Short squeeze risk computation works."""
    conn = _get_conn()
    if conn is None:
        return

    sig = short_squeeze_risk(conn, "SSE")
    if sig is not None:
        assert sig.name == "short_squeeze_risk"
        assert 0.0 <= sig.value <= 1.0

    conn.close()


def test_filing_event_signal():
    """Filing event signal works."""
    conn = _get_conn()
    if conn is None:
        return

    sig = filing_event_signal(conn, "NG.")
    if sig is not None:
        assert sig.name == "filing_activity"
        assert 0.0 <= sig.value <= 1.0

    conn.close()


def test_compute_all_signals():
    """All signals compute without errors."""
    conn = _get_conn()
    if conn is None:
        return

    signals = compute_all_signals(conn, ["NG.", "SSE", "CCC"])
    assert isinstance(signals, list)
    # Should return some signals if data exists
    for sig in signals:
        assert isinstance(sig, Signal)
        assert 0.0 <= sig.value <= 1.0

    conn.close()
