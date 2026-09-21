"""Companies House Basic Company Data monthly snapshot.

Downloads the full UK company population snapshot (~469 MB).
Updated monthly. Contains every active/dissolved company.

URL: https://download.companieshouse.gov.uk/
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

CH_BULK_BASE = "https://download.companieshouse.gov.uk"


def discover_company_snapshot_files() -> dict[str, Any]:
    """Discover available company snapshot files.

    Returns: {"files": [{"name": str, "size": int}], "latest_date": str}
    """
    client = httpx.Client(timeout=30, follow_redirects=True)
    try:
        resp = client.get(f"{CH_Bulk_BASE}/index.html")
        resp.raise_for_status()
        # For now, we know the pattern — improve later with HTML parsing
        return {"files": [], "latest_date": datetime.now().strftime("%Y-%m")}
    except Exception as e:
        log.warning("CH snapshot discovery error: %s", e)
        return {"files": [], "latest_date": ""}
    finally:
        client.close()


def download_company_snapshot(
    month: str | None = None,
    archive_dir: Path = Path("data/raw/ch_company_snapshot"),
) -> dict[str, Any] | None:
    """Download and archive the monthly company snapshot.

    This is a large file (~469 MB). We archive the raw file first.

    Args:
        month: Month to fetch (YYYY-MM format). Default: current month.
        archive_dir: Directory to archive raw files.

    Returns:
        Dict with metadata about the download.
    """
    if month is None:
        month = datetime.now().strftime("%Y-%m")

    date_dir = archive_dir / month
    date_dir.mkdir(parents=True, exist_ok=True)

    # Companies House offers these as CSV files
    # Pattern: BasicCompanyData-{YYYY-MM}.csv
    filename = f"BasicCompanyData-{month}.csv"
    url = f"{CH_BULK_BASE}/{filename}"

    client = httpx.Client(timeout=300, follow_redirects=True)
    try:
        resp = client.get(url)
        if resp.status_code == 404:
            log.warning("CH snapshot not found for %s: %s", month, url)
            return None

        resp.raise_for_status()

        # Archive raw CSV
        archive_path = date_dir / filename
        archive_path.write_bytes(resp.content)

        # Compute hash
        sha256 = hashlib.sha256(resp.content).hexdigest()

        return {
            "month": month,
            "source_url": url,
            "archive_path": str(archive_path),
            "sha256": sha256,
            "bytes": len(resp.content),
            "downloaded_at": datetime.now().isoformat(),
        }

    except Exception as e:
        log.warning("CH snapshot download error for %s: %s", month, e)
        return None
    finally:
        client.close()
