"""FCA TR-1 major shareholder notifications collector.

Under FCA DTR 5, major shareholders must notify when holdings cross
thresholds (1%, 2%, 3%, 5%, 10%, etc.). These are published via the
FCA National Storage Mechanism.

URL: https://www.fca.org.uk/markets/primary-markets/regulatory-disclosures/shareholding-notification-disclosure

Status: WIRED INTO RUN_ALL
- Registered in layer1/registry.py as "tr1_notifications" (enabled=True).
- Imported by powstock/collectors/__init__.py.
- Called by runner.py run_all().
- Currently just scrapes Investegate RNS headlines for "TR-1" — needs proper
  field parsing (shareholder, previous/new %, threshold crossed).
"""

from datetime import datetime
from typing import Any

import httpx


def fetch_tr1_announcements() -> list[dict[str, Any]]:
    """Fetch TR-1 major shareholder notifications.

    These are RNS announcements with category "Major Shareholding Notification".
    We scrape them from Investegate like other RNS.
    """
    from powstock.collectors.rns_announcements import fetch_rns_announcements

    # TR-1 announcements are typically "Holding(s) in Company" or "Major Shareholding"
    # We fetch recent RNS and filter for these types
    announcements = fetch_rns_announcements(max_pages=3)

    tr1_announcements = []
    for ann in announcements:
        headline = ann.headline.lower()
        if any(kw in headline for kw in [
            "holding", "major", "shareholding", "notification",
            "interest", "tr-1", "total voting rights",
        ]):
            tr1_announcements.append({
                "ticker": ann.ticker,
                "company": ann.company_name,
                "headline": ann.headline,
                "published_at": ann.published_at,
                "source_url": ann.source_url,
                "source": "investegate_tr1",
            })

    return tr1_announcements


def parse_tr1_details(html: str) -> dict[str, Any]:
    """Parse TR-1 notification details from HTML.

    Extracts:
    - shareholder name
    - previous voting rights %
    - new voting rights %
    - shares held
    - threshold crossed
    """
    import re

    details = {}

    # Extract shareholder name
    name_match = re.search(r'Shareholder.*?([A-Z][A-Z\s&]+)', html)
    if name_match:
        details["shareholder"] = name_match.group(1).strip()

    # Extract voting rights percentages
    pct_match = re.search(r'(\d+\.?\d*)%\s*(?:of|voting)', html)
    if pct_match:
        details["voting_rights_pct"] = float(pct_match.group(1))

    # Extract share count
    shares_match = re.search(r'([\d,]+)\s*(?:shares|voting rights)', html)
    if shares_match:
        details["shares"] = int(shares_match.group(1).replace(",", ""))

    # Extract threshold
    threshold_match = re.search(r'(\d+)%\s*threshold', html)
    if threshold_match:
        details["threshold_crossed"] = int(threshold_match.group(1))

    return details


def summarise_tr1_activity(announcements: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise TR-1 major shareholder activity."""
    if not announcements:
        return {"total": 0}

    return {
        "total": len(announcements),
        "tickers": list(set(a.get("ticker", "") for a in announcements)),
    }
