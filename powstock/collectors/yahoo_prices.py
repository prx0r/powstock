"""Yahoo Finance price collector for UK tickers.

Free, no API key. Fetches daily OHLCV from Yahoo Finance.
Uses .L suffix for LSE Main Market stocks.
"""

import logging
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
CACHE_TTL_S = 15 * 60
_cache: dict[str, tuple[float, list[dict]]] = {}
_client: httpx.Client | None = None

# Yahoo Finance symbol mapping for UK stocks
# .L suffix works for both Main Market and AIM
YAHOO_SYMBOLS: dict[str, str] = {
    "NG.": "NG.L",
    "SSE": "SSE.L",
    "DRX": "DRX.L",
    "CNA": "CNA.L",
    "CCC": "CCC.L",
    "CORD": "CORD.L",
    "BBOX": "BBOX.L",
    "SGRO": "SGRO.L",
    "RPI": "RPI.L",
    "CNC": "CNC.L",
    "IQE": "IQE.L",
    "XPP": "XPP.L",
    "VLX": "VLX.L",
    "TTG": "TTG.L",
    "DSCV": "DSCV.L",
    "SOLI": "SOLI.L",
    "PRE": "PRE.L",
    "TUN": "TUN.L",
    "ALL": "ALL.L",
    "SML": "SML.L",
    "HE1": "HE1.L",
    "RHL": "RHL.L",
    "CBTC": "CBTC.L",
    "IB1T": "IB1T.L",
    "BOLD": "BOLD.L",
}


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
    return _client


def fetch_ohlcv(ticker: str, days: int = 365) -> list[dict[str, Any]]:
    """Fetch daily OHLCV for a single ticker from Yahoo Finance.

    Returns list of dicts: {date, open, high, low, close, volume}
    """
    symbol = YAHOO_SYMBOLS.get(ticker)
    if not symbol:
        return []

    cache_key = f"yahoo:{symbol}"
    now = time.time()
    hit = _cache.get(cache_key)
    if hit and now - hit[0] < CACHE_TTL_S:
        return hit[1]

    try:
        client = _get_client()
        resp = client.get(
            f"{YAHOO_BASE}/{symbol}",
            params={
                "period1": int(time.time()) - (days * 86400),
                "period2": int(time.time()),
                "interval": "1d",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        result = data.get("chart", {}).get("result", [])
        if not result:
            return []

        timestamps = result[0].get("timestamp", [])
        indicators = result[0].get("indicators", {})
        quote = indicators.get("quote", [{}])[0]

        if not timestamps or not quote:
            return []

        rows = []
        for i, ts in enumerate(timestamps):
            try:
                open_price = quote.get("open", [None])[i]
                high = quote.get("high", [None])[i]
                low = quote.get("low", [None])[i]
                close = quote.get("close", [None])[i]
                volume = quote.get("volume", [0])[i]

                if close is None or close <= 0:
                    continue

                from datetime import datetime
                date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

                rows.append({
                    "date": date_str,
                    "open": float(open_price) if open_price else 0.0,
                    "high": float(high) if high else 0.0,
                    "low": float(low) if low else 0.0,
                    "close": float(close),
                    "volume": int(volume) if volume else 0,
                })
            except (ValueError, TypeError, IndexError):
                continue

        _cache[cache_key] = (now, rows)
        return rows

    except Exception as e:
        log.warning("Yahoo fetch error for %s: %s", ticker, e)
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
        "venue": "yahoo",
    }


def fetch_all_latest(tickers: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """Fetch latest prices for all universe tickers.

    Returns: {ticker: {price, pct_1d, asof, venue, ...}}
    """
    if tickers is None:
        tickers = list(YAHOO_SYMBOLS.keys())

    results = {}
    for ticker in tickers:
        latest = fetch_latest(ticker)
        if latest:
            results[ticker] = latest
        time.sleep(0.5)  # be nice to Yahoo

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
