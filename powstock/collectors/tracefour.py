"""Tracefour API collector — structured UK PDMR data.

Free API: 60 req/hr, key required (sign up at tracefour.com).
Endpoints:
  GET /v1/eu/uk — recent UK PDMR filings
  GET /v1/filings — SEC Form 4 (also has UK via ticker filter)
  GET /v1/clusters — cluster buys (3+ insiders same direction)
  GET /v1/streaks — consecutive buying streaks

Status: STALE
- Registered in layer1/registry.py as "tracefour" (enabled=True).
- NOT imported by powstock/collectors/__init__.py.
- NOT called by runner.py run_all().
- This is the PREFERRED source for UK insider data (structured, free, cluster/streak endpoints).
- BLOCKER: Needs TRACEFOUR_API_KEY in .env (sign up at tracefour.com, free).
- To activate: get API key, add to runner.py, replace Investegate PDMR as primary source.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

TRACEFOUR_BASE = "https://tracefour.com"
TRACEFOUR_API = "https://tracefour.com/v1"


@dataclass
class TracefourFiling:
    filing_id: str
    ticker: str
    company_name: str
    insider_name: str
    role: str
    direction: str  # P or S
    shares: int
    price: float
    value: float
    currency: str
    trade_date: str
    disclosed_date: str
    source_url: str
    raw: dict = field(default_factory=dict)


def _get_client(api_key: str | None = None) -> httpx.Client:
    """Create Tracefour API client."""
    headers = {"User-Agent": "powstocks/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return httpx.Client(timeout=30, follow_redirects=True, headers=headers)


def fetch_uk_filings(
    api_key: str | None = None,
    limit: int = 50,
    direction: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch recent UK PDMR filings from Tracefour.

    Args:
        api_key: Tracefour API key (free sign-up).
        limit: Max results (50 per page).
        direction: 'P' for purchases, 'S' for sales, None for all.

    Returns:
        List of filing dicts with structured PDMR data.
    """
    client = _get_client(api_key)
    try:
        params: dict[str, Any] = {"limit": limit}
        if direction:
            params["direction"] = direction

        resp = client.get(f"{TRACEFOUR_API}/eu/uk", params=params)
        resp.raise_for_status()
        data = resp.json()

        return data.get("data", [])
    finally:
        client.close()


def fetch_clusters(
    api_key: str | None = None,
    direction: str = "P",
) -> list[dict[str, Any]]:
    """Fetch cluster buys/sells (3+ insiders same direction in 60 days).

    Returns:
        List of cluster events with insider details.
    """
    client = _get_client(api_key)
    try:
        resp = client.get(f"{TRACEFOUR_API}/clusters", params={"direction": direction})
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    finally:
        client.close()


def fetch_streaks(
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch insider buying streaks (consecutive weeks).

    Returns:
        List of streaks with track records.
    """
    client = _get_client(api_key)
    try:
        resp = client.get(f"{TRACEFOUR_API}/streaks")
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    finally:
        client.close()


def fetch_filing(
    api_key: str | None = None,
    ticker: str | None = None,
    direction: str | None = None,
    min_value: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch filings with filters (works for UK tickers via .L suffix).

    Args:
        ticker: Filter by ticker (e.g. 'NG.L').
        direction: 'P' or 'S'.
        min_value: Minimum trade value in GBP/USD.
    """
    client = _get_client(api_key)
    try:
        params: dict[str, Any] = {"limit": limit}
        if ticker:
            params["ticker"] = ticker
        if direction:
            params["direction"] = direction
        if min_value:
            params["min_value"] = min_value

        resp = client.get(f"{TRACEFOUR_API}/filings", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    finally:
        client.close()


def fetch_static_uk() -> dict[str, Any]:
    """Fetch pre-rendered UK data (no key needed, CORS-open).

    Returns full UK filing dataset as JSON.
    """
    client = httpx.Client(timeout=30, follow_redirects=True)
    try:
        resp = client.get("https://tracefour.com/data/eu/uk.json")
        resp.raise_for_status()
        return resp.json()
    finally:
        client.close()


def classify_transaction(filing: dict[str, Any]) -> str:
    """Classify transaction nature from filing data.

    Returns one of:
    - OPEN_MARKET_PURCHASE (conviction buy)
    - OPEN_MARKET_SALE
    - OPTION_EXERCISE
    - RSU_VESTING
    - SHARE_AWARD
    - DIVIDEND_REINVESTMENT
    - TAX_SALE
    - UNKNOWN
    """
    # Tracefour provides direction (P/S) but not always the nature
    # For now, classify based on available fields
    direction = filing.get("direction", "")

    if direction == "P":
        # Purchases are more likely open-market conviction
        return "OPEN_MARKET_PURCHASE"
    elif direction == "S":
        return "OPEN_MARKET_SALE"

    return "UNKNOWN"


def is_conviction_buy(filing: dict[str, Any]) -> bool:
    """Determine if a purchase is a conviction buy.

    Conviction criteria:
    - Open market purchase (not option exercise/vesting)
    - Value > £50k
    - Director/CEO/CFO role
    """
    direction = filing.get("direction", "")
    value = filing.get("value", 0) or filing.get("value_gbp", 0) or 0
    role = (filing.get("role", "") or filing.get("reporter", {}).get("officer_title", "")).lower()

    if direction != "P":
        return False

    # High-value open market purchase
    if value >= 50000:
        return True

    # C-suite buying any amount
    c_suite = ["ceo", "cfo", "coo", "cto", "chair", "chief", "executive", "managing director"]
    if any(title in role for title in c_suite):
        return True

    return False


def summarise_uk_insider_activity(
    filings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarise UK insider activity for signal construction."""
    if not filings:
        return {"total": 0, "buys": 0, "sells": 0}

    buys = [f for f in filings if f.get("direction") == "P"]
    sells = [f for f in filings if f.get("direction") == "S"]

    buy_value = sum(f.get("value", 0) or f.get("value_gbp", 0) or 0 for f in buys)
    sell_value = sum(f.get("value", 0) or f.get("value_gbp", 0) or 0 for f in sells)

    return {
        "total": len(filings),
        "buys": len(buys),
        "sells": len(sells),
        "buy_value": buy_value,
        "sell_value": sell_value,
        "net_value": buy_value - sell_value,
        "conviction_buys": sum(1 for f in buys if is_conviction_buy(f)),
    }
