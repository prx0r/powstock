"""RNS announcement collector.

Scrapes Investegate for Regulatory News Service announcements.
Free, no API key. Parses headlines, company names, and metadata.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

log = logging.getLogger(__name__)

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

    On direct company pages, the company link is not in each row,
    so we use the ticker_filter as the known ticker.
    """
    announcements = []

    # Find all table rows
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)

    for row in rows:
        # Look for announcement rows - they have announcement links
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
        time_match = re.search(r'<td>(\d{1,2}\s+\w+\s+\d{4})</td>', row, re.DOTALL)
        published_at = ""
        if time_match:
            published_at = time_match.group(1).strip()

        # Extract link
        link_match = re.search(r'href="(https://www\.investegate\.co\.uk/announcement/[^"]+)"', row)
        source_url = ""
        if link_match:
            source_url = link_match.group(1)

        # Extract ticker from company link if present (global feed)
        ticker = ""
        company_name = ""
        company_match = re.search(r'href="https://www\.investegate\.ai/company/([^"]+)"[^>]*>([^<]+)\(([A-Z0-9.]+)\)</a>', row)
        if not company_match:
            company_match = re.search(r'href="https://www\.investegate\.co\.uk/company/([^"]+)"[^>]*>([^<]+)\(([A-Z0-9.]+)\)</a>', row)
        if company_match:
            ticker = company_match.group(3).strip()
            company_name = company_match.group(2).strip()

        # On direct company pages, extract ticker from announcement URL
        if not ticker and source_url:
            url_ticker_match = re.search(r'/announcement/rns/([^/]+)/', source_url)
            if url_ticker_match:
                slug = url_ticker_match.group(1)
                # Extract ticker after last -- (e.g. "national-grid--ng." → "ng.")
                parts = slug.split('--')
                ticker = parts[-1].rstrip('.').upper()
                # Restore trailing dot for tickers like NG.
                if '.' in slug.split('--')[-1]:
                    ticker = ticker + '.'

        # Use filter as fallback
        if not ticker and ticker_filter:
            ticker = ticker_filter

        # Filter by ticker if specified
        if ticker_filter and ticker.upper() != ticker_filter.upper():
            continue

        # Skip if no ticker at all
        if not ticker:
            continue

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
    """Fetch a page of announcements from Investegate.

    Args:
        ticker: Company ticker for direct page. None = global feed.
        page: Page number (1-indexed). Only used for global feed.
        page_size: Results per page (default 50).
    """
    client = httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )

    try:
        if ticker:
            # Direct company page — works reliably
            resp = client.get(f"https://www.investegate.co.uk/company/{ticker}")
        else:
            # Global feed
            params: dict[str, Any] = {"searchtype": "3"}
            if page > 1:
                params["page"] = str(page)
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
        # Investegate doesn't support per-ticker filtering via URL params.
        # Fetch global feed and filter by ticker after parsing.
        html = fetch_investegate_page(ticker=None, page=page)
        announcements = _parse_investegate_html(html, ticker_filter=ticker)
        all_announcements.extend(announcements)

        if not announcements:
            break

        time.sleep(1)  # respectful rate limiting

    return all_announcements


def fetch_universe_rns(
    max_pages: int = 2,
) -> list[RNSAnnouncement]:
    """Fetch RNS announcements and match to universe tickers by company name.

    Investegate doesn't support per-ticker search, so we:
    1. Fetch the global feed
    2. Match announcements to our universe by company name

    Returns:
        List of RNSAnnouncement records matched to universe tickers.
    """
    from powstock.universe import UNIVERSE

    # Build company name lookup (lowercase)
    name_to_ticker: dict[str, str] = {}
    for security in UNIVERSE:
        name_to_ticker[security.company.lower()] = security.ticker

    all_announcements = []

    for page in range(1, max_pages + 1):
        html = fetch_investegate_page(ticker=None, page=page)
        raw_announcements = _parse_investegate_html(html)

        for ann in raw_announcements:
            # Match by company name
            company_lower = ann.company_name.lower().strip()
            if company_lower in name_to_ticker:
                ann.ticker = name_to_ticker[company_lower]
                all_announcements.append(ann)

        time.sleep(1)

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
