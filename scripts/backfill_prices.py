"""Historical price backfill.

Fetches 1 year of daily OHLCV from Yahoo Finance for all universe tickers.
Stores in price_daily table.

Usage: python scripts/backfill_prices.py [--days 365]
"""

import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("data/powstock.db")


def backfill_prices(conn: sqlite3.Connection, days: int = 365) -> dict[str, int]:
    """Backfill historical prices for all universe tickers."""
    from powstock.universe import UNIVERSE
    from powstock.collectors.yahoo_prices import fetch_ohlcv

    results: dict[str, int] = {}

    for security in UNIVERSE:
        ticker = security.ticker
        try:
            rows = fetch_ohlcv(ticker, days=days)
            count = 0

            for row in rows:
                conn.execute(
                    """INSERT OR REPLACE INTO price_daily
                       (ticker, date, open, high, low, close, volume)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (ticker, row["date"], row["open"], row["high"],
                     row["low"], row["close"], row["volume"]),
                )
                count += 1

            results[ticker] = count
            print(f"  {ticker}: {count} days")

            time.sleep(0.5)  # rate limit

        except Exception as e:
            print(f"  {ticker}: ERROR {e}")
            results[ticker] = 0

    return results


def main():
    days = 365
    if len(sys.argv) > 1 and sys.argv[1] == "--days":
        days = int(sys.argv[2])

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    print(f"Backfilling {days} days of prices for all universe tickers...")

    results = backfill_prices(conn, days)
    conn.commit()

    total = sum(results.values())
    tickers_with_data = sum(1 for v in results.values() if v > 0)
    print(f"\nBackfill complete: {total} total rows across {tickers_with_data}/{len(results)} tickers")

    # Verify
    count = conn.execute("SELECT COUNT(*) FROM price_daily").fetchone()[0]
    print(f"price_daily table now has {count} rows")

    conn.close()


if __name__ == "__main__":
    main()
