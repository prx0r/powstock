"""Layer 2 signals — constructed from Layer 1 data.

No collectors. No domain scrapers. Just analysis over the tape.

Cross-source signals prove the garden's value:
a single source is interesting, multiple agreeing sources are predictive.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
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
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Single-source signals ──────────────────────────────────────────


def insider_pressure(conn: sqlite3.Connection, ticker: str) -> Signal | None:
    """Insider buying pressure. More buying = higher value."""
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
    pressure = min(total_buy / 1_000_000, 1.0) if total_buy > 0 else 0.0

    return Signal(
        name="insider_pressure",
        ticker=ticker,
        value=pressure,
        as_of="",
        confidence=min(deal_count / 5, 1.0),
        inputs=["insider_deals"],
        metadata={"total_buy_value": total_buy, "deal_count": deal_count},
    )


def short_interest_level(conn: sqlite3.Connection, ticker: str) -> Signal | None:
    """Current short interest level. High = more bearish positioning."""
    row = conn.execute(
        """SELECT position_pct FROM short_interest
           WHERE ticker=? ORDER BY effective_at DESC LIMIT 1""",
        (ticker,),
    ).fetchone()

    if not row or row[0] is None:
        return None

    short_pct = row[0]
    level = min(short_pct / 20.0, 1.0)

    return Signal(
        name="short_interest_level",
        ticker=ticker,
        value=level,
        as_of="",
        confidence=0.8 if short_pct > 0 else 0.0,
        inputs=["short_interest"],
        metadata={"short_pct": short_pct},
    )


def short_squeeze_risk(conn: sqlite3.Connection, ticker: str) -> Signal | None:
    """Squeeze risk = short interest level. (Price momentum added when available.)"""
    return short_interest_level(conn, ticker)


def filing_event_signal(conn: sqlite3.Connection, ticker: str) -> Signal | None:
    """Filing activity intensity. More corporate events = more activity."""
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


# ── Cross-source signals (the garden's real value) ─────────────────


def alignment_score(conn: sqlite3.Connection, ticker: str) -> Signal | None:
    """Cross-source alignment: insiders buying + shorts covering = strong signal.

    When multiple independent sources agree, the signal is more reliable.
    This is what a single-source screener cannot produce.

    Score components:
    - insider_buying: 0-1 (more buying = higher)
    - short_declining: 0-1 (shorts covering = higher)
    - alignment = geometric mean of available signals
    """
    # Get insider signal
    insider = insider_pressure(conn, ticker)
    insider_val = insider.value if insider else None

    # Get short interest (we want the level, not squeeze risk)
    short = short_interest_level(conn, ticker)
    short_val = short.value if short else None

    # Build alignment from available signals
    signals: list[float] = []
    inputs: list[str] = []

    if insider_val is not None:
        signals.append(insider_val)
        inputs.append("insider_deals")

    if short_val is not None:
        # Invert: low short interest = bullish, high = bearish
        signals.append(1.0 - short_val)
        inputs.append("short_interest")

    if not signals:
        return None

    # Geometric mean (conservative — requires multiple sources to agree)
    product = 1.0
    for s in signals:
        product *= max(s, 0.01)
    alignment = product ** (1.0 / len(signals))

    return Signal(
        name="alignment_score",
        ticker=ticker,
        value=round(alignment, 4),
        as_of="",
        confidence=min(len(signals) / 2, 1.0),  # 2 sources = full confidence
        inputs=inputs,
        metadata={
            "insider_val": insider_val,
            "short_val": short_val,
            "sources_used": len(signals),
        },
    )


def anomaly_score(conn: sqlite3.Connection, ticker: str) -> Signal | None:
    """Detect unusual patterns across sources.

    An anomaly is when one source deviates significantly from its norm.
    High insider buying with high short interest = divergence = anomaly.
    """
    insider = insider_pressure(conn, ticker)
    short = short_interest_level(conn, ticker)

    if insider is None or short is None:
        return None

    # Divergence: insiders buying (high) but shorts also high = unusual
    divergence = abs(insider.value - (1.0 - short.value))

    # High divergence = high anomaly
    anomaly = divergence

    return Signal(
        name="anomaly_score",
        ticker=ticker,
        value=round(anomaly, 4),
        as_of="",
        confidence=0.7,
        inputs=["insider_deals", "short_interest"],
        metadata={
            "insider_bullish": insider.value,
            "short_bearish": short.value,
            "divergence": divergence,
        },
    )


def composite_score(conn: sqlite3.Connection, ticker: str) -> Signal | None:
    """Weighted composite of all available signals.

    Weights:
    - alignment: 40% (cross-source signals are most reliable)
    - insider: 25% (informed money)
    - short: 20% (crowdedness)
    - filing: 15% (corporate activity)
    """
    signals: dict[str, tuple[float, float]] = {}  # name: (value, weight)

    ins = insider_pressure(conn, ticker)
    if ins:
        signals["insider"] = (ins.value, 0.25)

    short = short_interest_level(conn, ticker)
    if short:
        signals["short"] = (short.value, 0.20)

    filing = filing_event_signal(conn, ticker)
    if filing:
        signals["filing"] = (filing.value, 0.15)

    align = alignment_score(conn, ticker)
    if align:
        signals["alignment"] = (align.value, 0.40)

    if not signals:
        return None

    # Normalize weights
    total_weight = sum(w for _, w in signals.values())
    if total_weight == 0:
        return None

    weighted_sum = sum(v * w for v, w in signals.values())
    composite = weighted_sum / total_weight

    return Signal(
        name="composite_score",
        ticker=ticker,
        value=round(composite, 4),
        as_of="",
        confidence=min(len(signals) / 4, 1.0),
        inputs=["insider_deals", "short_interest", "company_profiles"],
        metadata={
            "components": {k: round(v, 4) for k, (v, _) in signals.items()},
            "weights_used": {k: round(w, 2) for k, (_, w) in signals.items()},
        },
    )


# ── Aggregation ────────────────────────────────────────────────────


ALL_SIGNAL_FNS = [
    insider_pressure,
    short_interest_level,
    filing_event_signal,
    alignment_score,
    anomaly_score,
    composite_score,
]


def compute_all_signals(
    conn: sqlite3.Connection,
    tickers: list[str] | None = None,
) -> list[Signal]:
    """Compute all Layer 2 signals for given tickers."""
    if tickers is None:
        from powstock.universe import UNIVERSE
        tickers = [s.ticker for s in UNIVERSE]

    signals: list[Signal] = []
    for ticker in tickers:
        for compute_fn in ALL_SIGNAL_FNS:
            sig = compute_fn(conn, ticker)
            if sig is not None:
                signals.append(sig)

    return signals


def signal_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Summary of all signals across the universe."""
    signals = compute_all_signals(conn)

    by_name: dict[str, list[Signal]] = {}
    for s in signals:
        by_name.setdefault(s.name, []).append(s)

    summary: dict[str, Any] = {}
    for name, sigs in by_name.items():
        values = [s.value for s in sigs]
        summary[name] = {
            "count": len(sigs),
            "mean": sum(values) / len(values) if values else 0,
            "min": min(values) if values else 0,
            "max": max(values) if values else 0,
        }

    return summary
