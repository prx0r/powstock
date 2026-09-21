"""Takeover Panel disclosures collector.

During offer periods, investors holding >=1% of relevant securities must disclose
positions and dealings under Rule 8.3. The Panel publishes disclosure tables in
web, XLS, CSV, XML formats.

URL: https://www.thetakeoverpanel.org.uk/disclosure
"""

from datetime import datetime
from typing import Any

import httpx

TAKEOVER_PANEL_URL = "https://www.thetakeoverpanel.org.uk/disclosure"
TAKEOVER_PANEL_DOWNLOADS = "https://www.thetakeoverpanel.org.uk/downloads/disclosure-forms"
TAKEOVER_PANEL_STATS = "https://www.thetakeoverpanel.org.uk/communications/transaction-statistics"


def fetch_disclosure_table() -> str:
    """Fetch the current disclosure table from the Takeover Panel."""
    client = httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        resp = client.get(TAKEOVER_PANEL_URL)
        resp.raise_for_status()
        return resp.text
    finally:
        client.close()


def fetch_transaction_statistics() -> dict[str, Any]:
    """Fetch transaction statistics from the Takeover Panel."""
    client = httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        resp = client.get(TAKEOVER_PANEL_STATS)
        resp.raise_for_status()
        return {"url": TAKEOVER_PANEL_STATS, "length": len(resp.text)}
    finally:
        client.close()


def parse_disclosure_forms(html: str) -> list[dict[str, Any]]:
    """Parse disclosure forms from the Takeover Panel HTML."""
    import re

    disclosures = []

    # Find disclosure links (Form 8.3, Form 8.5, etc.)
    form_pattern = re.compile(
        r'href="([^"]*disclosure[^"]*\.pdf)"[^>]*>([^<]+)</a>',
        re.IGNORECASE,
    )

    for match in form_pattern.finditer(html):
        url = match.group(1)
        title = match.group(2).strip()

        disclosures.append({
            "url": url,
            "title": title,
            "source": "takeover_panel",
            "fetched_at": datetime.now().isoformat(),
        })

    return disclosures


def summarise_panel_activity(disclosures: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise Takeover Panel activity."""
    if not disclosures:
        return {"total": 0}

    # Count by form type
    form_types = {}
    for d in disclosures:
        title = d.get("title", "")
        if "8.3" in title:
            form_types["form_8_3"] = form_types.get("form_8_3", 0) + 1
        elif "8.5" in title:
            form_types["form_8_5"] = form_types.get("form_8_5", 0) + 1
        else:
            form_types["other"] = form_types.get("other", 0) + 1

    return {
        "total": len(disclosures),
        "form_types": form_types,
    }
