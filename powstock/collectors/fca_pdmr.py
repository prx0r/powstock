"""FCA PDMR insider dealing collector.

Scrapes the FCA National Storage Mechanism for Director/PDMR Dealings.
Free, no API key. Parses structured notification forms.
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

FCA_NSM_URL = "https://data.fca.org.uk/artefacts/NSM/RNS/"
FCA_NSM_SEARCH = "https://data.fca.org.uk/artefacts/NSM/RNS/Search"


@dataclass
class InsiderDeal:
    ticker: str
    company_name: str
    director_name: str
    position: str  # Dir, CEO, CFO, etc.
    action: str  # BUY, SELL, OPTION_GRANT, OPTION_EXERCISE
    price: float
    shares: int
    total_value: float
    trade_date: str
    filing_date: str
    venue: str  # LSE, AIM, SETSqx
    notification_url: str
    source: str = "fca_nsm"
    raw: dict = field(default_factory=dict)


def _parse_pdmr_html(html: str, ticker_filter: str | None = None) -> list[InsiderDeal]:
    """Parse PDMR notification HTML into structured deals.

    The NSM search returns HTML pages with notification summaries.
    Each notification has structured fields in a form layout.
    """
    deals = []

    # Find all notification blocks
    # The NSM uses a consistent HTML structure for PDMR notifications
    notification_pattern = re.compile(
        r'<div[^>]*class="[^"]*notification[^"]*"[^>]*>(.*?)</div>',
        re.DOTALL,
    )

    # Extract company name from header
    company_pattern = re.compile(r'<h[23][^>]*>(.*?)</h[23]>', re.DOTALL)
    # Extract TIDM (ticker) from links
    tidm_pattern = re.compile(r'href="[^"]*stock/([^"/]+)"')
    # Extract director name
    name_pattern = re.compile(r'Name of.*?<[^>]*>(.*?)<', re.DOTALL)
    # Extract position/role
    position_pattern = re.compile(r'Position/Status.*?<[^>]*>(.*?)<', re.DOTALL)
    # Extract transaction details
    price_pattern = re.compile(r'Price.*?(\d+\.?\d*)', re.DOTALL)
    volume_pattern = re.compile(r'Volume.*?(\d[\d,]*)', re.DOTALL)
    date_pattern = re.compile(r'(?:Transaction|Notification)\s+Date.*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', re.DOTALL)

    # Simpler approach: parse the full text for known patterns
    # PDMR notifications have a standard format

    # Find all "Director/PDMR Dealings" sections
    sections = re.split(r'Director/PDMR', html, flags=re.IGNORECASE)

    for section in sections[1:]:  # skip first (before any match)
        deal_data = {}

        # Company name
        company_match = company_pattern.search(section)
        if company_match:
            deal_data["company_name"] = re.sub(r'<[^>]+>', '', company_match.group(1)).strip()

        # TIDM
        tidm_match = tidm_pattern.search(section)
        if tidm_match:
            deal_data["ticker"] = tidm_match.group(1).strip()

        # Filter by ticker if specified
        if ticker_filter and deal_data.get("ticker", "").upper() != ticker_filter.upper():
            continue

        # Director name
        name_match = name_pattern.search(section)
        if name_match:
            deal_data["director_name"] = re.sub(r'<[^>]+>', '', name_match.group(1)).strip()

        # Position
        pos_match = position_pattern.search(section)
        if pos_match:
            deal_data["position"] = re.sub(r'<[^>]+>', '', pos_match.group(1)).strip()

        # Price
        price_match = price_pattern.search(section)
        if price_match:
            deal_data["price"] = float(price_match.group(1).replace(',', ''))

        # Volume
        vol_match = volume_pattern.search(section)
        if vol_match:
            deal_data["shares"] = int(vol_match.group(1).replace(',', ''))

        # Date
        date_match = date_pattern.search(section)
        if date_match:
            deal_data["trade_date"] = date_match.group(1)

        # Determine action from text
        section_lower = section.lower()
        if "purchased" in section_lower or "bought" in section_lower:
            deal_data["action"] = "BUY"
        elif "sold" in section_lower or "disposal" in section_lower:
            deal_data["action"] = "SELL"
        elif "option" in section_lower and ("grant" in section_lower or "exercise" in section_lower):
            deal_data["action"] = "OPTION_GRANT" if "grant" in section_lower else "OPTION_EXERCISE"
        else:
            deal_data["action"] = "UNKNOWN"

        if "ticker" in deal_data and "director_name" in deal_data:
            deals.append(InsiderDeal(
                ticker=deal_data.get("ticker", ""),
                company_name=deal_data.get("company_name", ""),
                director_name=deal_data.get("director_name", ""),
                position=deal_data.get("position", ""),
                action=deal_data.get("action", "UNKNOWN"),
                price=deal_data.get("price", 0.0),
                shares=deal_data.get("shares", 0),
                total_value=deal_data.get("price", 0.0) * deal_data.get("shares", 0),
                trade_date=deal_data.get("trade_date", ""),
                filing_date=datetime.now().strftime("%Y-%m-%d"),
                venue="LSE",
                notification_url=FCA_NSM_URL,
                raw=deal_data,
            ))

    return deals


def fetch_pdmr_page(page: int = 1, page_size: int = 50) -> str:
    """Fetch a page of PDMR notifications from FCA NSM search."""
    client = httpx.Client(timeout=30, follow_redirects=True)

    try:
        resp = client.get(
            FCA_NSM_SEARCH,
            params={
                "page": page,
                "pageSize": page_size,
                "headlineType": "Director/PDMR Dealings",
            },
        )
        resp.raise_for_status()
        return resp.text
    finally:
        client.close()


def fetch_pdmr_notifications(
    ticker: str | None = None,
    max_pages: int = 5,
) -> list[InsiderDeal]:
    """Fetch PDMR notifications from FCA NSM.

    Args:
        ticker: Filter by specific ticker (e.g. "HE1"). None = all.
        max_pages: Maximum pages to fetch (50 results per page).

    Returns:
        List of InsiderDeal structured records.
    """
    all_deals = []

    for page in range(1, max_pages + 1):
        html = fetch_pdmr_page(page=page)
        deals = _parse_pdmr_html(html, ticker_filter=ticker)
        all_deals.extend(deals)

        if not deals:
            break

        time.sleep(1)  # respectful rate limiting

    return all_deals


def fetch_ticker_insiders(ticker: str, max_pages: int = 3) -> list[dict[str, Any]]:
    """Fetch recent insider dealings for a specific ticker.

    Simplified interface returning dicts for pipeline consumption.
    """
    deals = fetch_pdmr_notifications(ticker=ticker, max_pages=max_pages)
    return [
        {
            "ticker": d.ticker,
            "company": d.company_name,
            "director": d.director_name,
            "position": d.position,
            "action": d.action,
            "price": d.price,
            "shares": d.shares,
            "value": d.total_value,
            "trade_date": d.trade_date,
            "filing_date": d.filing_date,
            "source": d.source,
        }
        for d in deals
    ]


def summarise_insider_activity(deals: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise insider activity for a ticker.

    Returns aggregated metrics for signal construction.
    """
    if not deals:
        return {"ticker": None, "total_deals": 0}

    buys = [d for d in deals if d["action"] == "BUY"]
    sells = [d for d in deals if d["action"] == "SELL"]

    return {
        "ticker": deals[0]["ticker"],
        "total_deals": len(deals),
        "buys": len(buys),
        "sells": len(sells),
        "total_buy_value": sum(d["value"] for d in buys),
        "total_sell_value": sum(d["value"] for d in sells),
        "net_value": sum(d["value"] for d in buys) - sum(d["value"] for d in sells),
        "unique_directors": len(set(d["director"] for d in deals)),
        "buy_sell_ratio": len(buys) / len(sells) if sells else float("inf"),
    }
