"""Build daily state from fact tables.

Materializes pow_company_state_daily from the Layer 1 fact tables.
This is the bridge between Layer 1 (data garden) and Layer 2 (analysis).

Usage: python scripts/build_daily_state.py [--date 2026-09-21]

The script is idempotent: same inputs → same daily state.
"""

import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path("data/powstock.db")


def build_daily_state(conn: sqlite3.Connection, target_date: date) -> list[dict]:
    """Build daily state records for all universe tickers on a given date."""
    from powstock.universe import UNIVERSE
    from powstock.schema.daily_state import build_daily_state as _build

    states = []

    for security in UNIVERSE:
        # Gather data from fact tables
        insider_data = _get_insider_data(conn, security.ticker, target_date)
        ownership_data = _get_ownership_data(conn, security.ticker)
        financial_data = _get_financial_data(conn, security.ticker)
        market_data = _get_market_data(conn, security.ticker, target_date)
        filing_events = _get_filing_events(conn, security.ticker, target_date)

        state = _build(
            ticker=security.ticker,
            state_date=target_date,
            insider_data=insider_data,
            ownership_data=ownership_data,
            financial_data=financial_data,
            filing_events=filing_events,
            market_data=market_data,
        )

        states.append(state.to_dict())

    return states


def _get_insider_data(conn: sqlite3.Connection, ticker: str, target_date: date) -> dict | None:
    """Get insider metrics for a ticker up to target_date."""
    row = conn.execute("""
        SELECT action, SUM(value) as total, COUNT(*) as cnt
        FROM insider_deals
        WHERE ticker = ? AND effective_at <= ?
        GROUP BY action
    """, (ticker, target_date.isoformat())).fetchall()

    if not row:
        return None

    buys_7d = 0.0
    buys_90d = 0.0
    sells_7d = 0.0

    seven_days_ago = (target_date - __import__('datetime').timedelta(days=7)).isoformat()
    ninety_days_ago = (target_date - __import__('datetime').timedelta(days=90)).isoformat()

    for action, total, cnt in row:
        if action == "Purchase":
            buys_90d += total or 0
            # 7d subset
            r = conn.execute("""
                SELECT COALESCE(SUM(value), 0) FROM insider_deals
                WHERE ticker = ? AND action = 'Purchase' AND effective_at >= ? AND effective_at <= ?
            """, (ticker, seven_days_ago, target_date.isoformat())).fetchone()
            buys_7d = r[0] if r else 0

    return {
        "buy_value_7d": buys_7d,
        "buy_value_90d": buys_90d,
        "sell_value_7d": sells_7d,
        "conviction_buy_count": 0,
        "net_conviction_value": buys_7d - sells_7d,
    }


def _get_ownership_data(conn: sqlite3.Connection, ticker: str) -> dict | None:
    """Get ownership metrics for a ticker."""
    row = conn.execute("""
        SELECT position_pct FROM short_interest
        WHERE ticker = ? ORDER BY effective_at DESC LIMIT 1
    """, (ticker,)).fetchone()

    if not row:
        return None

    return {
        "psc_state": "",
        "delta_7d": 0.0,
        "delta_30d": 0.0,
    }


def _get_financial_data(conn: sqlite3.Connection, ticker: str) -> dict | None:
    """Get latest financial data for a ticker."""
    row = conn.execute("""
        SELECT sic_codes, officers_count, charges_count, psc_count
        FROM company_profiles
        WHERE ticker = ? ORDER BY observed_at DESC LIMIT 1
    """, (ticker,)).fetchone()

    if not row:
        return None

    return {
        "turnover": None,
        "cash": None,
        "creditors_due_within_one_year": None,
        "creditors_due_after_one_year": None,
        "average_number_employees_during_period": None,
        "tangible_fixed_assets": None,
    }


def _get_market_data(conn: sqlite3.Connection, ticker: str, target_date: date) -> dict | None:
    """Get market data for a ticker on target_date."""
    row = conn.execute("""
        SELECT open, high, low, close, volume
        FROM price_daily
        WHERE ticker = ? AND date = ?
    """, (ticker, target_date.isoformat())).fetchone()

    if not row:
        return None

    return {
        "price": row[3],  # close
        "market_cap": None,
        "volume": row[4],
    }


def _get_filing_events(conn: sqlite3.Connection, ticker: str, target_date: date) -> list[dict] | None:
    """Get filing events for a ticker around target_date."""
    # Filing events don't have ticker in this schema, return empty for now
    return None


def main():
    """Build daily state from CLI."""
    target = date.today()
    if len(sys.argv) > 1 and sys.argv[1] == "--date":
        target = date.fromisoformat(sys.argv[2])

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    print(f"Building daily state for {target}...")

    states = build_daily_state(conn, target)

    # Store in a new table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pow_company_state_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            state_json TEXT NOT NULL,
            UNIQUE(date, ticker)
        )
    """)

    for state in states:
        conn.execute("""
            INSERT OR REPLACE INTO pow_company_state_daily (date, ticker, state_json)
            VALUES (?, ?, ?)
        """, (target.isoformat(), state["ticker"], json.dumps(state, default=str)))

    conn.commit()

    # Summary
    count = conn.execute(
        "SELECT COUNT(*) FROM pow_company_state_daily WHERE date = ?",
        (target.isoformat(),),
    ).fetchone()[0]
    print(f"Built {count} daily state records for {target}")

    # Show sample
    for state in states[:3]:
        nullable_fields = [k for k, v in state.items() if v is None and k not in ("date", "ticker", "entity_id", "company_number", "isin", "lei")]
        print(f"  {state['ticker']}: price={state.get('price')}, employees={state.get('employees')}, "
              f"insider_buy_7d={state.get('insider_buy_value_7d')} ({len(nullable_fields)} NULL fields)")

    conn.close()


if __name__ == "__main__":
    main()
