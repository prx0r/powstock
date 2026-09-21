"""RNS announcement collector.

Scrapes Investegate for Regulatory News Service announcements.
Free, no API key. Parses headlines, company names, and metadata.
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

INVESTEGATE_URL = "https://www.investegate.co.uk/Index.aspx"


@dataclass
class RNSAnnouncement:
    ticker: str
    company_name: str
    headline: str
    category: str  # RNS, PRN, EQS
    published_at: str
    source_url: str
    source: str = "investegate"
    raw: dict = field(default_factory=dict)


def _parse_investegate_html(html: str, ticker_filter: str | None = None) -> list[RNSAnnouncement]:
    """Parse Investegate page HTML into structured announcements.

    Investegate shows announcements in table rows:
    - Time (td)
    - Source (td with RNS/PRN/EQS)
    - Company (td with link containing "Company Name (TICKER)")
    - Headline (td with announcement link)
    """
    announcements = []

    # Find all table rows
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)

    for row in rows:
        # Look for announcement rows - they have company links and announcement links
        # Pattern: <a href="...company/TICKER">Company Name (TICKER)</a>
        # and: <a class="announcement-link" href="...">Headline</a>

        # Extract company name and ticker
        company_match = re.search(r'href="https://www\.investegate\.ai/company/([^"]+)"[^>]*>([^<]+)\(([A-Z0-9.]+)\)</a>', row)
        if not company_match:
            # Try alternate pattern
            company_match = re.search(r'href="https://www\.investegate\.co\.uk/company/([^"]+)"[^>]*>([^<]+)\(([A-Z0-9.]+)\)</a>', row)

        if not company_match:
            continue

        ticker = company_match.group(3).strip()
        company_name = company_match.group(2).strip()

        # Filter by ticker if specified
        if ticker_filter and ticker.upper() != ticker_filter.upper():
            continue

        # Extract headline
        headline_match = re.search(r'class="announcement-link"[^>]*>(.*?)</a>', row, re.DOTALL)
        if not headline_match:
            continue

        headline = re.sub(r'<[^>]+>', '', headline_match.group(1)).strip()

        # Extract source (RNS, PRN, EQS)
        source_match = re.search(r'class="[^"]*source-([^"]+)"[^>]*>(.*?)</a>', row, re.DOTALL)
        category = "RNS"
        if source_match:
            category = re.sub(r'<[^>]+>', '', source_match.group(2)).strip()

        # Extract time
        time_match = re.search(r'<td>(\d{1,2}\s+\w+\s+\d{4}\s+\d{1,2}:\d{2}\s+[AP]M)</td>', row, re.DOTALL)
        published_at = ""
        if time_match:
            published_at = time_match.group(1).strip()

        # Extract link
        link_match = re.search(r'href="(https://www\.investegate\.co\.uk/announcement/[^"]+)"', row)
        source_url = ""
        if link_match:
            source_url = link_match.group(1)

        announcements.append(RNSAnnouncement(
            ticker=ticker,
            company_name=company_name,
            headline=headline,
            category=category,
            published_at=published_at,
            source_url=source_url,
            raw={"row": row[:200]},  # truncate for storage
        ))

    return announcements


def fetch_investegate_page(
    ticker: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> str:
    """Fetch a page of announcements from Investegate."""
    client = httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )

    try:
        params = {"searchtype": "3"}  # All companies
        if ticker:
            params["search"] = ticker

        resp = client.get(INVESTEGATE_URL, params=params)
        resp.raise_for_status()
        return resp.text
    finally:
        client.close()


def fetch_rns_announcements(
    ticker: str | None = None,
    max_pages: int = 3,
) -> list[RNSAnnouncement]:
    """Fetch RNS announcements from Investegate.

    Args:
        ticker: Filter by specific TIDM. None = all recent.
        max_pages: Maximum pages to fetch (50 results per page).

    Returns:
        List of RNSAnnouncement records.
    """
    all_announcements = []

    for page in range(1, max_pages + 1):
        html = fetch_investegate_page(ticker=ticker, page=page)
        announcements = _parse_investegate_html(html, ticker_filter=ticker)
        all_announcements.extend(announcements)

        if not announcements:
            break

        time.sleep(1)  # respectful rate limiting

    return all_announcements


def fetch_ticker_rns(ticker: str, max_pages: int = 3) -> list[dict[str, Any]]:
    """Fetch recent RNS announcements for a specific ticker.

    Simplified interface returning dicts for pipeline consumption.
    """
    announcements = fetch_rns_announcements(ticker=ticker, max_pages=max_pages)
    return [
        {
            "ticker": a.ticker,
            "company": a.company_name,
            "headline": a.headline,
            "category": a.category,
            "published_at": a.published_at,
            "source_url": a.source_url,
            "source": a.source,
        }
        for a in announcements
    ]


def summarise_rns_activity(announcements: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise RNS activity for a ticker.

    Returns aggregated metrics for signal construction.
    """
    if not announcements:
        return {"ticker": None, "total_announcements": 0}

    # Categorise announcements
    categories = {}
    for a in announcements:
        cat = a.get("category", "Unknown")
        categories[cat] = categories.get(cat, 0) + 1

    # Look for specific announcement types
    has_director_dealing = any("Director" in a.get("headline", "") or "PDMR" in a.get("headline", "") for a in announcements)
    has_results = any("Results" in a.get("headline", "") or "Annual" in a.get("headline", "") for a in announcements)
    has_holding = any("Holding" in a.get("headline", "") or "Major" in a.get("headline", "") for a in announcements)

    return {
        "ticker": announcements[0]["ticker"],
        "total_announcements": len(announcements),
        "categories": categories,
        "has_director_dealing": has_director_dealing,
        "has_results": has_results,
        "has_holding_change": has_holding,
        "latest_headline": announcements[0]["headline"] if announcements else "",
        "latest_date": announcements[0]["published_at"] if announcements else "",
    }
