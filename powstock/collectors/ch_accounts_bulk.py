"""Companies House XBRL accounts bulk archive.

Downloads and archives daily/monthly XBRL accounts bulk files.
These contain structured financial data for UK companies.

URL: https://download.companieshouse.gov.uk/
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

CH_BULK_BASE = "https://download.companieshouse.gov.uk"


def download_accounts_bulk(
    date_str: str | None = None,
    archive_dir: Path = Path("data/raw/ch_accounts"),
) -> dict[str, Any] | None:
    """Download and archive the daily XBRL accounts bulk file.

    These files are large but invaluable for financial analysis.

    Args:
        date_str: Date to fetch (YYYY-MM-DD). Default: yesterday.
        archive_dir: Directory to archive raw files.

    Returns:
        Dict with metadata about the download.
    """
    if date_str is None:
        date_str = (datetime.now() - __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")

    date_dir = archive_dir / date_str
    date_dir.mkdir(parents=True, exist_ok=True)

    # Companies House XBRL accounts bulk files
    filename = f"ch-{date_str}-accounts.zip"
    url = f"{CH_BULK_BASE}/{filename}"

    client = httpx.Client(timeout=300, follow_redirects=True)
    try:
        resp = client.get(url)
        if resp.status_code == 404:
            # Try alternate naming
            filename = f"Accounts-{date_str}.zip"
            url = f"{CH_BULK_BASE}/{filename}"
            resp = client.get(url)

        if resp.status_code == 404:
            log.warning("CH accounts bulk not found for %s", date_str)
            return None

        resp.raise_for_status()

        # Archive raw ZIP
        archive_path = date_dir / filename
        archive_path.write_bytes(resp.content)

        sha256 = hashlib.sha256(resp.content).hexdigest()

        return {
            "date": date_str,
            "source_url": url,
            "archive_path": str(archive_path),
            "sha256": sha256,
            "bytes": len(resp.content),
            "downloaded_at": datetime.now().isoformat(),
        }

    except Exception as e:
        log.warning("CH accounts bulk download error for %s: %s", date_str, e)
        return None
    finally:
        client.close()
