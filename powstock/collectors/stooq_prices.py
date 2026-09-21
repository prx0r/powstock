"""Stooq price collector for UK tickers.

Free, no API key. Fetches daily OHLCV from stooq.com.
Reuses the pattern from fish/fish/services/prices.py.
"""

import csv
import io
import time
from typing import Any

import httpx

from powstock.universe import STOOQ_SYMBOLS

STOOQ_BASE = "https://stooq.com/q/d/l/"
CACHE_TTL_S = 15 * 60
_cache: dict[str, tuple[float, list[dict]]] = {}
_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=30, follow_redirects=True)
    return _client


def fetch_ohlcv(ticker: str, days: int = 365) -> list[dict[str, Any]]:
    """Fetch daily OHLCV for a single ticker from Stooq.

    Returns list of dicts: {date, open, high, low, close, volume}
    """
    symbol = STOOQ_SYMBOLS.get(ticker)
    if not symbol:
        return []

    cache_key = f"stooq:{symbol}"
    now = time.time()
    hit = _cache.get(cache_key)
    if hit and now - hit[0] < CACHE_TTL_S:
        return hit[1]

    try:
        client = _get_client()
        resp = client.get(
            STOOQ_BASE,
            params={"s": symbol, "d1": "20000101", "d2": "21000101", "i": "d"},
        )
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        rows = []
        for row in reader:
            try:
                rows.append({
                    "date": row["Date"],
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                })
            except (ValueError, KeyError):
                continue

        _cache[cache_key] = (now, rows)
        return rows

    except Exception:
        return hit[1] if hit else []


def fetch_latest(ticker: str) -> dict[str, Any] | None:
    """Fetch latest price snapshot for a ticker.

    Returns: {ticker, price, prev_close, pct_1d, open, high, low, volume, asof, venue}
    """
    rows = fetch_ohlcv(ticker)
    if len(rows) < 2:
        return None

    prev = rows[-2]
    curr = rows[-1]

    if prev["close"] <= 0 or curr["close"] <= 0:
        return None

    pct_1d = (curr["close"] - prev["close"]) / prev["close"] * 100

    return {
        "ticker": ticker,
        "price": curr["close"],
        "prev_close": prev["close"],
        "pct_1d": round(pct_1d, 4),
        "open": curr["open"],
        "high": curr["high"],
        "low": curr["low"],
        "volume": curr["volume"],
        "asof": curr["date"],
        "venue": "stooq",
    }


def fetch_all_latest(tickers: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """Fetch latest prices for all universe tickers.

    Returns: {ticker: {price, pct_1d, asof, venue, ...}}
    """
    if tickers is None:
        tickers = list(STOOQ_SYMBOLS.keys())

    results = {}
    for ticker in tickers:
        latest = fetch_latest(ticker)
        if latest:
            results[ticker] = latest
        time.sleep(0.5)  # be nice to Stooq

    return results


def get_moves(tickers: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """Compatibility function matching fish's get_moves interface.

    Returns: {ticker: {price, pct_1d, asof, venue}}
    """
    all_latest = fetch_all_latest(tickers)
    return {
        t: {"price": v["price"], "pct_1d": v["pct_1d"], "asof": v["asof"], "venue": v["venue"]}
        for t, v in all_latest.items()
    }


def unmoved(tickers: list[str], threshold_pct: float = 2.0) -> list[str]:
    """Return tickers whose 1-day move is below threshold.

    These are stocks where repricing may not have happened yet.
    """
    moves = get_moves(tickers)
    return [t for t in tickers if t in moves and abs(moves[t]["pct_1d"]) < threshold_pct]
