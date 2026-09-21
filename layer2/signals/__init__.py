"""Layer 2 signals — constructed from Layer 1 data.

No collectors. No domain scrapers. Just analysis over the tape.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass
class Signal:
    """A signal derived from Layer 1 observations."""
    name: str
    ticker: str
    value: float
    as_of: str
    confidence: float  # 0-1, how much data supports this
    inputs: list[str]  # which Layer 1 tables fed this


def insider_pressure(conn: sqlite3.Connection, ticker: str) -> Signal | None:
    """Compute insider buying pressure for a ticker.

    Sources: insider_deals from Layer 1.
    """
    rows = conn.execute(
        """SELECT action, SUM(value) as total_value, COUNT(*) as deal_count
           FROM insider_deals WHERE ticker=? AND action='Purchase'
           GROUP BY action""",
        (ticker,),
    ).fetchall()

    if not rows:
        return None

    total_buy = sum(r[1] for r in rows if r[1])
    deal_count = sum(r[2] for r in rows)

    # Simple pressure: more buying = higher pressure
    pressure = min(total_buy / 1_000_000, 1.0) if total_buy > 0 else 0.0

    return Signal(
        name="insider_pressure",
        ticker=ticker,
        value=pressure,
        as_of="",
        confidence=min(deal_count / 5, 1.0),
        inputs=["insider_deals"],
    )


def short_squeeze_risk(conn: sqlite3.Connection, ticker: str) -> Signal | None:
    """Compute short squeeze risk for a ticker.

    Sources: short_interest from Layer 1.
    High short interest + positive price movement = squeeze risk.
    """
    row = conn.execute(
        """SELECT position_pct FROM short_interest
           WHERE ticker=? ORDER BY report_date DESC LIMIT 1""",
        (ticker,),
    ).fetchone()

    if not row or row[0] is None:
        return None

    short_pct = row[0]

    # High short interest = higher squeeze risk
    risk = min(short_pct / 20.0, 1.0)  # 20%+ short = max risk

    return Signal(
        name="short_squeeze_risk",
        ticker=ticker,
        value=risk,
        as_of="",
        confidence=0.8 if short_pct > 0 else 0.0,
        inputs=["short_interest"],
    )


def filing_event_signal(conn: sqlite3.Connection, ticker: str) -> Signal | None:
    """Compute filing event intensity for a ticker.

    Sources: company_profiles (filing counts) from Layer 1.
    More filings = more corporate activity.
    """
    row = conn.execute(
        """SELECT officers_count, charges_count, psc_count
           FROM company_profiles WHERE ticker=?
           ORDER BY observed_at DESC LIMIT 1""",
        (ticker,),
    ).fetchone()

    if not row:
        return None

    officers, charges, psc = row
    activity = (officers or 0) + (charges or 0) + (psc or 0)
    intensity = min(activity / 50, 1.0)

    return Signal(
        name="filing_activity",
        ticker=ticker,
        value=intensity,
        as_of="",
        confidence=0.9,
        inputs=["company_profiles"],
    )


def compute_all_signals(conn: sqlite3.Connection, tickers: list[str] | None = None) -> list[Signal]:
    """Compute all Layer 2 signals for given tickers."""
    if tickers is None:
        from powstock.universe import UNIVERSE
        tickers = [s.ticker for s in UNIVERSE]

    signals: list[Signal] = []
    for ticker in tickers:
        for compute_fn in [insider_pressure, short_squeeze_risk, filing_event_signal]:
            sig = compute_fn(conn, ticker)
            if sig is not None:
                signals.append(sig)

    return signals
