"""Commodity Prices collector.

Fetches physical commodity prices relevant to the POW supply chain.
Free, no API key required.

Sources:
- metals-api.com (free tier)
- Yahoo Finance (GC=F, SI=F, HG=F)
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

YAHOO_COMMODITIES = {
    "gold": "GC=F",
    "silver": "SI=F",
    "copper": "HG=F",
    "platinum": "PL=F",
    "palladium": "PA=F",
}

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"


@dataclass
class CommodityPrice:
    date: str
    commodity: str  # "gold", "silver", "copper", etc.
    price: float
    currency: str
    unit: str  # "oz", "lb"
    source: str


def fetch_commodity_price(
    commodity: str,
    symbol: str,
    client: httpx.Client,
) -> CommodityPrice | None:
    """Fetch spot price from Yahoo Finance."""
    try:
        import time
        resp = client.get(
            f"{YAHOO_CHART_URL}/{symbol}",
            params={
                "period1": int(time.time()) - 86400,
                "period2": int(time.time()),
                "interval": "1d",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        result = data.get("chart", {}).get("result", [])
        if result:
            quote = result[0].get("indicators", {}).get("quote", [{}])[0]
            close = quote.get("close", [None])[0]
            ts = result[0].get("timestamp", [None])[0]
            if close and ts:
                from datetime import datetime
                date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                unit = "lb" if commodity in ("copper",) else "oz"
                return CommodityPrice(
                    date=date,
                    commodity=commodity,
                    price=float(close),
                    currency="USD",
                    unit=unit,
                    source="yahoo_finance",
                )
    except Exception as e:
        log.warning("Yahoo commodity error for %s: %s", commodity, e)
    return None


def fetch_all_commodity_prices() -> list[CommodityPrice]:
    """Fetch all available commodity prices."""
    prices = []

    with httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for commodity, symbol in YAHOO_COMMODITIES.items():
            price = fetch_commodity_price(commodity, symbol, client)
            if price:
                prices.append(price)

    return prices
