"""Finnhub insider transactions collector.

Free API: 60 calls/min, no payment required.
Covers UK stocks via ticker.L format.
URL: https://finnhub.io/docs/api/insider-transactions
"""

from datetime import datetime, timedelta
from typing import Any

import httpx

FINNHUB_BASE = "https://finnhub.io/api/v1"


def fetch_insider_transactions(
    ticker: str,
    api_key: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Fetch insider transactions for a UK-listed stock.

    Args:
        ticker: Ticker symbol (e.g. 'NG' for National Grid).
        api_key: Finnhub API key (free registration).
        limit: Max results per call.

    Returns:
        List of insider transaction dicts.
    """
    if not api_key:
        return []

    # UK tickers need .L suffix for Finnhub
    finnhub_symbol = f"{ticker}.L"

    client = httpx.Client(timeout=30)
    try:
        resp = client.get(
            f"{FINNHUB_BASE}/stock/insider-transactions",
            params={
                "symbol": finnhub_symbol,
                "limit": limit,
                "token": api_key,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        transactions = []
        for item in data.get("data", []):
            transactions.append({
                "ticker": ticker,
                "finnhub_symbol": finnhub_symbol,
                "name": item.get("name", ""),
                "share": item.get("share", ""),
                "change": item.get("change", 0),
                "transaction_date": item.get("transactionDate", ""),
                "transaction_price": item.get("transactionPrice", 0),
                "transaction_volume": item.get("transactionVolume", 0),
                "transaction_code": item.get("transactionCode", ""),
                "transaction_price_total": item.get("transactionPriceTotal", 0),
                "filing_date": item.get("filingDate", ""),
                "filing_url": item.get("filingUrl", ""),
                "source": "finnhub",
            })

        return transactions

    except Exception as e:
        print(f"  Finnhub error for {ticker}: {e}")
        return []
    finally:
        client.close()


def fetch_universe_insiders(
    api_key: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch insider transactions for all universe tickers.

    Returns: {ticker: [transactions]}
    """
    from powstock.universe import UNIVERSE

    results: dict[str, list[dict[str, Any]]] = {}

    for security in UNIVERSE:
        transactions = fetch_insider_transactions(security.ticker, api_key)
        if transactions:
            results[security.ticker] = transactions

    return results


def classify_finnhub_code(code: str) -> str:
    """Classify Finnhub transaction code."""
    code_map = {
        "P": "OPEN_MARKET_PURCHASE",
        "S": "OPEN_MARKET_SALE",
        "A": "SHARE_AWARD",
        "M": "OPTION_EXERCISE",
        "G": "GIFT",
        "F": "TAX_SALE",
        "D": "DIVIDEND",
        "V": "VESTING",
        "W": "VOLUNTARY_REPORT",
    }
    return code_map.get(code, "UNKNOWN")


def summarise_finnhub_activity(
    transactions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarise Finnhub insider activity."""
    if not transactions:
        return {"total": 0}

    buys = [t for t in transactions if t.get("transaction_code") == "P"]
    sells = [t for t in transactions if t.get("transaction_code") == "S"]

    buy_value = sum(
        abs(t.get("transaction_price_total", 0)) for t in buys
    )
    sell_value = sum(
        abs(t.get("transaction_price_total", 0)) for t in sells
    )

    return {
        "total": len(transactions),
        "buys": len(buys),
        "sells": len(sells),
        "buy_value": buy_value,
        "sell_value": sell_value,
        "net_value": buy_value - sell_value,
        "latest": transactions[0] if transactions else None,
    }
