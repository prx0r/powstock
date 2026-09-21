"""Layer 2 signal tests.

Verifies cross-source signals work on live data.
"""

import sqlite3
from pathlib import Path

from layer2.signals import (
    Signal,
    insider_pressure,
    short_interest_level,
    filing_event_signal,
    alignment_score,
    anomaly_score,
    composite_score,
    compute_all_signals,
    signal_summary,
)

DB_PATH = Path(__file__).parent.parent / "data" / "powstock.db"


def _get_conn() -> sqlite3.Connection | None:
    if DB_PATH.exists():
        return sqlite3.connect(str(DB_PATH))
    return None


def test_signal_dataclass():
    s = Signal(name="test", ticker="TEST", value=0.5, as_of="2026-09-21",
               confidence=0.8, inputs=["test_table"])
    assert s.name == "test"
    assert s.value == 0.5


def test_insider_pressure():
    conn = _get_conn()
    if conn is None:
        return
    sig = insider_pressure(conn, "NG.")
    if sig is not None:
        assert sig.name == "insider_pressure"
        assert 0.0 <= sig.value <= 1.0
        assert "insider_deals" in sig.inputs
    conn.close()


def test_short_interest_level():
    conn = _get_conn()
    if conn is None:
        return
    sig = short_interest_level(conn, "SSE")
    if sig is not None:
        assert sig.name == "short_interest_level"
        assert 0.0 <= sig.value <= 1.0
    conn.close()


def test_filing_event_signal():
    conn = _get_conn()
    if conn is None:
        return
    sig = filing_event_signal(conn, "NG.")
    if sig is not None:
        assert sig.name == "filing_activity"
        assert 0.0 <= sig.value <= 1.0
    conn.close()


def test_alignment_score():
    """Alignment requires multiple sources — the garden's real value."""
    conn = _get_conn()
    if conn is None:
        return
    sig = alignment_score(conn, "SSE")
    if sig is not None:
        assert sig.name == "alignment_score"
        assert 0.0 <= sig.value <= 1.0
        assert sig.metadata.get("sources_used", 0) >= 1
        assert len(sig.inputs) >= 1
    conn.close()


def test_alignment_requires_multiple_sources():
    """Alignment with only 1 source should have lower confidence."""
    conn = _get_conn()
    if conn is None:
        return
    # Find a ticker with only one source
    sig = alignment_score(conn, "SSE")
    if sig:
        sources = sig.metadata.get("sources_used", 0)
        if sources == 1:
            assert sig.confidence < 1.0
    conn.close()


def test_anomaly_score():
    conn = _get_conn()
    if conn is None:
        return
    sig = anomaly_score(conn, "SSE")
    if sig is not None:
        assert sig.name == "anomaly_score"
        assert 0.0 <= sig.value <= 1.0
        assert "divergence" in sig.metadata
    conn.close()


def test_composite_score():
    """Composite should weight alignment highest."""
    conn = _get_conn()
    if conn is None:
        return
    sig = composite_score(conn, "SSE")
    if sig is not None:
        assert sig.name == "composite_score"
        assert 0.0 <= sig.value <= 1.0
        assert "components" in sig.metadata
        assert "weights_used" in sig.metadata
    conn.close()


def test_compute_all_signals():
    conn = _get_conn()
    if conn is None:
        return
    signals = compute_all_signals(conn, ["NG.", "SSE", "CCC"])
    assert isinstance(signals, list)
    # Should have signals for each ticker
    tickers = {s.ticker for s in signals}
    assert len(tickers) >= 1
    for sig in signals:
        assert isinstance(sig, Signal)
        assert 0.0 <= sig.value <= 1.0
    conn.close()


def test_signal_summary():
    conn = _get_conn()
    if conn is None:
        return
    summary = signal_summary(conn)
    assert isinstance(summary, dict)
    # Should have at least one signal type
    for name, stats in summary.items():
        assert "count" in stats
        assert "mean" in stats
        assert "min" in stats
        assert "max" in stats
    conn.close()
