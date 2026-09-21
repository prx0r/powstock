"""RNS announcement collector.

Scrapes LSE and FCA NSM for Regulatory News Service announcements.
Free for private investors. Parses headlines, summaries, and metadata.
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

LSE_NEWS_URL = "https://www.londonstockexchange.com/news"
FCA_NSM_URL = "https://data.fca.org.uk/artefacts/NSM/RNS/"


@dataclass
class RNSAnnouncement:
    ticker: str
    company_name: str
    headline: str
    category: str  # Regulatory, Non-regulatory, PDMR, etc.
    summary: str
    published_at: str
    source_url: str
    rns_id: str
    source: str = "lse_rns"
    raw: dict = field(default_factory=dict)


def _parse_lse_news_html(html: str, ticker_filter: str | None = None) -> list[RNSAnnouncement]:
    """Parse LSE news page HTML into structured announcements."""
    announcements = []

    # Find news items in the HTML
    # LSE uses a consistent structure with headlines in <a> tags
    item_pattern = re.compile(
        r'<a[^>]*href="(/news/[^"]+)"[^>]*>.*?<span[^>]*>(.*?)</span>.*?<span[^>]*>(.*?)</span>',
        re.DOTALL | re.IGNORECASE,
    )

    # Also try a simpler pattern for headline extraction
    headline_pattern = re.compile(
        r'<h[34][^>]*>.*?<a[^>]*>(.*?)</a>.*?</h[34]>',
        re.DOTALL | re.IGNORECASE,
    )

    # Extract TIDM from links
    tidm_pattern = re.compile(r'/stock/([A-Z0-9.]+)/', re.IGNORECASE)

    # Split by news items
    items = re.split(r'class="[^"]*news-item[^"]*"', html, flags=re.IGNORECASE)

    for item in items[1:]:  # skip first chunk
        announcement = {}

        # Find headline
        headline_match = headline_pattern.search(item)
        if headline_match:
            announcement["headline"] = re.sub(r'<[^>]+>', '', headline_match.group(1)).strip()

        # Find TIDM
        tidm_match = tidm_pattern.search(item)
        if tidm_match:
            announcement["ticker"] = tidm_match.group(1).strip()

        # Filter by ticker if specified
        if ticker_filter and announcement.get("ticker", "").upper() != ticker_filter.upper():
            continue

        # Find date
        date_pattern = re.compile(r'(\d{1,2}\s+\w+\s+\d{4}|\d{2}/\d{2}/\d{4})')
        date_match = date_pattern.search(item)
        if date_match:
            announcement["published_at"] = date_match.group(1)

        # Find source URL
        url_pattern = re.compile(r'href="(/news/[^"]+)"')
        url_match = url_pattern.search(item)
        if url_match:
            announcement["source_url"] = f"https://www.londonstockexchange.com{url_match.group(1)}"

        if "headline" in announcement and "ticker" in announcement:
            announcements.append(RNSAnnouncement(
                ticker=announcement.get("ticker", ""),
                company_name="",
                headline=announcement.get("headline", ""),
                category="Unknown",
                summary="",
                published_at=announcement.get("published_at", ""),
                source_url=announcement.get("source_url", ""),
                rns_id=announcement.get("source_url", "").split("/")[-1] if announcement.get("source_url") else "",
                raw=announcement,
            ))

    return announcements


def _parse_nsm_html(html: str, ticker_filter: str | None = None) -> list[RNSAnnouncement]:
    """Parse FCA NSM search results HTML."""
    announcements = []

    # NSM has a table-like structure
    row_pattern = re.compile(
        r'<tr[^>]*>.*?</tr>',
        re.DOTALL | re.IGNORECASE,
    )

    # Find all links to individual announcements
    link_pattern = re.compile(
        r'href="(/artefacts/NSM/RNS/[^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE,
    )

    # Extract TIDM from announcement text
    tidm_pattern = re.compile(r'\b([A-Z0-9]{1,6})\b')

    # Split by table rows
    rows = re.split(r'<tr[^>]*>', html, flags=re.IGNORECASE)

    for row in rows[1:]:  # skip header
        link_match = link_pattern.search(row)
        if not link_match:
            continue

        url = link_match.group(1)
        text = re.sub(r'<[^>]+>', '', link_match.group(2)).strip()

        # Try to extract TIDM from the text
        tidm_match = tidm_pattern.search(text)

        announcement = RNSAnnouncement(
            ticker=tidm_match.group(1) if tidm_match else "",
            company_name="",
            headline=text[:200],
            category="RNS",
            summary="",
            published_at="",
            source_url=f"https://data.fca.org.uk{url}",
            rns_id=url.split("/")[-1] if url else "",
        )

        if ticker_filter and announcement.ticker.upper() != ticker_filter.upper():
            continue

        announcements.append(announcement)

    return announcements


def fetch_lse_news(
    ticker: str | None = None,
    max_pages: int = 3,
) -> list[RNSAnnouncement]:
    """Fetch RNS announcements from LSE website.

    Args:
        ticker: Filter by specific TIDM. None = all.
        max_pages: Maximum pages to fetch.

    Returns:
        List of RNSAnnouncement records.
    """
    all_announcements = []
    client = httpx.Client(timeout=30, follow_redirects=True)

    try:
        for page in range(1, max_pages + 1):
            params = {"page": page}
            if ticker:
                params["companies"] = ticker

            resp = client.get(LSE_NEWS_URL, params=params)
            resp.raise_for_status()

            announcements = _parse_lse_news_html(resp.text, ticker_filter=ticker)
            all_announcements.extend(announcements)

            if not announcements:
                break

            time.sleep(1)  # respectful rate limiting
    finally:
        client.close()

    return all_announcements


def fetch_nsm_news(
    ticker: str | None = None,
    max_pages: int = 3,
) -> list[RNSAnnouncement]:
    """Fetch RNS announcements from FCA NSM.

    Args:
        ticker: Filter by TIDM. None = all.
        max_pages: Maximum pages to fetch.

    Returns:
        List of RNSAnnouncement records.
    """
    all_announcements = []
    client = httpx.Client(timeout=30, follow_redirects=True)

    try:
        for page in range(1, max_pages + 1):
            resp = client.get(
                FCA_NSM_URL,
                params={"page": page, "pageSize": 50},
            )
            resp.raise_for_status()

            announcements = _parse_nsm_html(resp.text, ticker_filter=ticker)
            all_announcements.extend(announcements)

            if not announcements:
                break

            time.sleep(1)
    finally:
        client.close()

    return all_announcements


def fetch_ticker_rns(ticker: str, max_pages: int = 3) -> list[dict[str, Any]]:
    """Fetch recent RNS announcements for a specific ticker.

    Simplified interface returning dicts for pipeline consumption.
    """
    announcements = fetch_lse_news(ticker=ticker, max_pages=max_pages)
    return [
        {
            "ticker": a.ticker,
            "headline": a.headline,
            "category": a.category,
            "published_at": a.published_at,
            "source_url": a.source_url,
            "rns_id": a.rns_id,
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

    return {
        "ticker": announcements[0]["ticker"],
        "total_announcements": len(announcements),
        "categories": categories,
        "latest_headline": announcements[0]["headline"] if announcements else "",
        "latest_date": announcements[0]["published_at"] if announcements else "",
        "has_regulatory": "Regulatory" in categories,
        "has_pdmr": any("PDMR" in k for k in categories),
    }
