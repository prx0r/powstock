"""FCA National Storage Mechanism — official regulatory announcements.

Since 3 November 2025, PIPs must submit regulatory announcements via FCA's
structured schema/API with metadata including issuer names, LEIs, and categories.

This is the canonical regulatory tape. Investegate is a mirror/backup.

URL: https://www.fca.org.uk/markets/primary-markets/regulatory-disclosures/national-storage-mechanism
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

FCA_NSM_BASE = "https://www.fca.org.uk"
FCA_NSM_URL = f"{FCA_NSM_BASE}/markets/primary-markets/regulatory-disclosures/national-storage-mechanism"


def fetch_nsm_page(max_pages: int = 5) -> list[dict[str, Any]]:
    """Fetch regulatory announcements from FCA NSM.

    Returns list of announcement metadata dicts.
    """
    client = httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    announcements = []

    try:
        for page in range(1, max_pages + 1):
            params = {"page": page} if page > 1 else {}
            resp = client.get(FCA_NSM_URL, params=params)
            resp.raise_for_status()

            # Store raw HTML for later parsing
            html = resp.text

            # Parse announcements (simplified — real implementation would use proper HTML parsing)
            import re
            # Find announcement links
            links = re.findall(r'href="([^"]*announcement[^"]*)"', html, re.IGNORECASE)

            for link in links:
                if not link.startswith("http"):
                    link = f"{FCA_NSM_BASE}{link}"
                announcements.append({
                    "url": link,
                    "page": page,
                    "fetched_at": datetime.now().isoformat(),
                })

            if not links:
                break

    except Exception as e:
        log.warning("FCA NSM fetch error: %s", e)
    finally:
        client.close()

    return announcements


def download_nsm_artifact(
    url: str,
    archive_dir: Path = Path("data/raw/fca_nsm"),
) -> dict[str, Any] | None:
    """Download and archive a single NSM announcement.

    Archives the raw HTML/PDF before any parsing.
    """
    client = httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        resp = client.get(url)
        resp.raise_for_status()

        # Determine content type
        content_type = resp.headers.get("content-type", "text/html")
        ext = ".html" if "html" in content_type else ".pdf" if "pdf" in content_type else ".bin"

        # Generate filename from URL
        import re
        slug = re.sub(r'[^a-zA-Z0-9]', '_', url.split("/")[-1])[:50]
        filename = f"{slug}{ext}"

        # Archive
        archive_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        day_dir = archive_dir / today
        day_dir.mkdir(parents=True, exist_ok=True)

        archive_path = day_dir / filename
        archive_path.write_bytes(resp.content)

        sha256 = hashlib.sha256(resp.content).hexdigest()

        return {
            "url": url,
            "archive_path": str(archive_path),
            "sha256": sha256,
            "bytes": len(resp.content),
            "content_type": content_type,
            "downloaded_at": datetime.now().isoformat(),
        }

    except Exception as e:
        log.warning("FCA NSM download error for %s: %s", url, e)
        return None
    finally:
        client.close()
