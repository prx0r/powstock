"""Takeover Panel disclosures collector.

During offer periods, investors holding >=1% of relevant securities must disclose
positions and dealings under Rule 8.3. The Panel publishes disclosure tables in
web, XLS, CSV, XML formats.

URL: https://www.thetakeoverpanel.org.uk/disclosure

Status: STALE
- Registered in layer1/registry.py as "takeover_panel" (enabled=True).
- Imported by powstock/collectors/__init__.py.
- Tested in tests/test_collectors.py (integration test).
- NOT called by runner.py run_all().
- To activate: add to runner.py run_all().
"""

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

TAKEOVER_PANEL_URL = "https://www.thetakeoverpanel.org.uk/disclosure"
TAKEOVER_PANEL_DOWNLOADS = "https://www.thetakeoverpanel.org.uk/downloads/disclosure-forms"
TAKEOVER_PANEL_STATS = "https://www.thetakeoverpanel.org.uk/communications/transaction-statistics"
ARCHIVE_DIR = Path("data/raw/takeover_panel")


def fetch_disclosure_table(archive: bool = True) -> dict[str, Any]:
    """Fetch the current disclosure table from the Takeover Panel.

    Returns dict with keys: html, sha256, archived_path (if archived).
    """
    client = httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        resp = client.get(TAKEOVER_PANEL_URL)
        resp.raise_for_status()
        html = resp.text
        sha256 = hashlib.sha256(html.encode()).hexdigest()

        result: dict[str, Any] = {
            "html": html,
            "sha256": sha256,
            "fetched_at": datetime.now().isoformat(),
        }

        if archive:
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime("%Y-%m-%d")
            archive_path = ARCHIVE_DIR / f"disclosure-{date_str}.html"
            archive_path.write_text(html)
            result["archived_path"] = str(archive_path)
            log.info("Archived takeover panel disclosure to %s", archive_path)

        return result
    except httpx.HTTPStatusError as e:
        log.warning("Takeover Panel HTTP %s: %s", e.response.status_code, e)
        return {"html": "", "sha256": "", "error": str(e)}
    except Exception as e:
        log.warning("Takeover Panel fetch error: %s", e)
        return {"html": "", "sha256": "", "error": str(e)}
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
        return {
            "url": TAKEOVER_PANEL_STATS,
            "length": len(resp.text),
            "sha256": hashlib.sha256(resp.text.encode()).hexdigest(),
            "fetched_at": datetime.now().isoformat(),
        }
    except httpx.HTTPStatusError as e:
        log.warning("Takeover stats HTTP %s: %s", e.response.status_code, e)
        return {"error": str(e)}
    except Exception as e:
        log.warning("Takeover stats error: %s", e)
        return {"error": str(e)}
    finally:
        client.close()


def parse_disclosure_forms(html: str) -> list[dict[str, Any]]:
    """Parse disclosure forms from the Takeover Panel HTML.

    Returns list of dicts with url, title, form_type, source.
    """
    disclosures = []

    # Find disclosure links (Form 8.3, Form 8.5, etc.)
    form_pattern = re.compile(
        r'href="([^"]*disclosure[^"]*\.pdf)"[^>]*>([^<]+)</a>',
        re.IGNORECASE,
    )

    for match in form_pattern.finditer(html):
        url = match.group(1)
        title = match.group(2).strip()

        # Classify form type
        form_type = "other"
        if "8.3" in title:
            form_type = "form_8_3"
        elif "8.5" in title:
            form_type = "form_8_5"
        elif "9.3" in title:
            form_type = "form_9_3"

        disclosures.append({
            "url": url,
            "title": title,
            "form_type": form_type,
            "source": "takeover_panel",
            "fetched_at": datetime.now().isoformat(),
        })

    return disclosures


def summarise_panel_activity(disclosures: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise Takeover Panel activity."""
    if not disclosures:
        return {"total": 0}

    # Count by form type
    form_types: dict[str, int] = {}
    for d in disclosures:
        ft = d.get("form_type", "other")
        form_types[ft] = form_types.get(ft, 0) + 1

    return {
        "total": len(disclosures),
        "form_types": form_types,
    }
