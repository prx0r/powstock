"""Companies House PSC daily snapshot collector.

Downloads the daily PSC (Persons with Significant Control) bulk dataset.
This is a ZIP file (or multipart ZIPs) containing NDJSON records of all PSCs in the UK.
Updated daily before 10am GMT.

URL: https://download.companieshouse.gov.uk/en_pscdata.html

As of September 2026, PSC snapshots are split into 32 parts:
  psc-snapshot-2026-09-21_1of32.zip
  ...
  psc-snapshot-2026-09-21_32of32.zip

There is also a single combined file:
  persons-with-significant-control-snapshot-2026-09-21.zip
"""

import hashlib
import json
import logging
import re
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

CH_PSC_INDEX = "https://download.companieshouse.gov.uk/en_pscdata.html"
CH_PSC_BASE = "https://download.companieshouse.gov.uk"


def discover_psc_files(date_str: str) -> dict[str, Any]:
    """Discover available PSC snapshot files for a given date.

    Returns: {
        "single_file": "persons-with-significant-control-snapshot-{date}.zip" or None,
        "multipart_parts": ["psc-snapshot-{date}_1of32.zip", ...],
        "total_parts": int,
    }
    """
    client = httpx.Client(timeout=30, follow_redirects=True)
    try:
        resp = client.get(CH_PSC_INDEX)
        resp.raise_for_status()
        html = resp.text

        # Find single file
        single_match = re.search(
            rf'href="(persons-with-significant-control-snapshot-{re.escape(date_str)}\.zip)"',
            html, re.IGNORECASE,
        )
        single_file = single_match.group(1) if single_match else None

        # Find multipart files
        multipart_pattern = re.compile(
            rf'href="(psc-snapshot-{re.escape(date_str)}_(\d+)of(\d+)\.zip)"',
            re.IGNORECASE,
        )
        multipart_matches = multipart_pattern.findall(html)
        multipart_parts = sorted(
            [m[0] for m in multipart_matches],
            key=lambda x: int(re.search(r'_(\d+)of', x).group(1)),
        )
        total_parts = int(multipart_matches[0][2]) if multipart_matches else 0

        return {
            "single_file": single_file,
            "multipart_parts": multipart_parts,
            "total_parts": total_parts,
        }
    except Exception as e:
        log.warning("PSC discovery error: %s", e)
        return {"single_file": None, "multipart_parts": [], "total_parts": 0}
    finally:
        client.close()


def download_psc_snapshot(
    date: datetime | None = None,
    archive_dir: Path = Path("data/raw/psc"),
) -> dict[str, Any] | None:
    """Download and archive the daily PSC snapshot.

    Archives raw ZIP files before parsing. This is Level 1 raw preservation.

    Args:
        date: Date to fetch (default: yesterday).
        archive_dir: Directory to archive raw ZIPs.

    Returns:
        Dict with keys: records, requested_date, source_date, archive_paths, sha256.
        Or None if unavailable.
    """
    if date is None:
        date = datetime.now() - timedelta(days=1)

    requested_date_str = date.strftime("%Y-%m-%d")
    date_dir = archive_dir / requested_date_str
    date_dir.mkdir(parents=True, exist_ok=True)

    # Discover available files
    files = discover_psc_files(requested_date_str)
    log.info("PSC files for %s: single=%s, parts=%d",
             requested_date_str, files["single_file"], files["total_parts"])

    # Try single file first, then multipart
    source_date = requested_date_str
    source_url = ""
    all_records: list[dict] = []
    archive_paths: list[str] = []

    client = httpx.Client(timeout=120, follow_redirects=True)

    try:
        if files["single_file"]:
            # Download single file
            source_url = f"{CH_PSC_BASE}/{files['single_file']}"
            resp = client.get(source_url)

            if resp.status_code == 404:
                # Try previous day
                prev_date = date - timedelta(days=1)
                source_date = prev_date.strftime("%Y-%m-%d")
                prev_files = discover_psc_files(source_date)
                if prev_files["single_file"]:
                    source_url = f"{CH_PSC_BASE}/{prev_files['single_file']}"
                    resp = client.get(source_url)

            if resp.status_code == 200:
                # Archive raw ZIP
                zip_path = date_dir / files["single_file"]
                zip_path.write_bytes(resp.content)
                archive_paths.append(str(zip_path))

                # Parse records from ZIP
                all_records = _parse_zip_content(resp.content)

        elif files["multipart_parts"]:
            # Download all parts
            source_date_requested = requested_date_str
            for part_name in files["multipart_parts"]:
                source_url = f"{CH_PSC_BASE}/{part_name}"
                resp = client.get(source_url)

                if resp.status_code == 404:
                    # Try previous day's parts
                    prev_date = date - timedelta(days=1)
                    source_date = prev_date.strftime("%Y-%m-%d")
                    prev_part_name = part_name.replace(requested_date_str, source_date)
                    source_url = f"{CH_PSC_BASE}/{prev_part_name}"
                    resp = client.get(source_url)

                if resp.status_code == 200:
                    # Archive raw ZIP part
                    zip_path = date_dir / part_name
                    zip_path.write_bytes(resp.content)
                    archive_paths.append(str(zip_path))

                    # Parse records from this part
                    part_records = _parse_zip_content(resp.content)
                    all_records.extend(part_records)
                else:
                    log.warning("PSC part %s returned %d", part_name, resp.status_code)
        else:
            log.warning("No PSC files found for %s", requested_date_str)
            return None

        # Compute SHA256 of all archived data
        combined_hash = hashlib.sha256()
        for p in archive_paths:
            combined_hash.update(Path(p).read_bytes())

        return {
            "records": all_records,
            "requested_date": requested_date_str,
            "source_date": source_date,
            "source_url": source_url,
            "archive_paths": archive_paths,
            "sha256": combined_hash.hexdigest(),
            "total_parts": len(archive_paths),
        }

    except Exception as e:
        log.warning("PSC download error: %s", e)
        return None
    finally:
        client.close()


def _parse_zip_content(zip_bytes: bytes) -> list[dict]:
    """Parse NDJSON records from a ZIP file."""
    records = []
    try:
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            json_files = [f for f in zf.namelist() if f.endswith(".json")]
            for json_file in json_files:
                with zf.open(json_file) as jf:
                    for line in jf:
                        line = line.strip()
                        if line:
                            try:
                                record = json.loads(line)
                                records.append(record)
                            except json.JSONDecodeError:
                                continue
    except Exception as e:
        log.warning("ZIP parse error: %s", e)
    return records


def parse_psc_record(record: dict[str, Any]) -> dict[str, Any]:
    """Parse a raw PSC record into normalized format."""
    try:
        company = record.get("company", {})
        psc = record.get("data", [{}])[0] if record.get("data") else {}

        return {
            "company_number": company.get("company_number", ""),
            "company_name": company.get("company_name", ""),
            "company_status": company.get("company_status", ""),
            "psc_name": psc.get("name", ""),
            "psc_kind": psc.get("kind", ""),
            "nature_of_control": psc.get("natures_of_control", []),
            "notified_on": psc.get("notified_on", ""),
            "ceased_on": psc.get("ceased_on"),
            "address": psc.get("address", {}),
            "country_of_residence": psc.get("country_of_residence", ""),
            "nationality": psc.get("nationality", ""),
            "date_of_birth": psc.get("date_of_birth"),
        }
    except Exception as e:
        log.warning("PSC record parse error: %s", e)
        return {}


def fetch_universe_psc(
    universe_tickers: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch current PSC data for universe companies via REST API.

    This hits the live Companies House PSC endpoints, NOT the bulk snapshot.
    Returns: {ticker: [psc_records]}
    """
    from powstock.universe import UNIVERSE

    if universe_tickers is None:
        universe_tickers = [s.ticker for s in UNIVERSE]

    from powstock.collectors.companies_house import fetch_universe_companies
    companies = fetch_universe_companies()

    results: dict[str, list[dict[str, Any]]] = {}

    for ticker in universe_tickers:
        if ticker not in companies:
            continue
        company_number = companies[ticker].get("company_number", "")
        if not company_number:
            continue
        psc_list = _fetch_company_psc(company_number)
        if psc_list:
            results[ticker] = psc_list

    return results


def _fetch_company_psc(company_number: str) -> list[dict[str, Any]]:
    """Fetch PSC for a single company via REST API."""
    from powstock.collectors.companies_house import CH_BASE, _get_auth

    client = httpx.Client(timeout=30)
    try:
        resp = client.get(
            f"{CH_BASE}/company/{company_number}/persons-with-significant-control",
            auth=_get_auth(),
            params={"items_per_page": 50},
        )
        resp.raise_for_status()
        data = resp.json()

        psc_list = []
        for item in data.get("items", []):
            psc_list.append({
                "name": item.get("name", ""),
                "kind": item.get("kind", ""),
                "nature_of_control": item.get("natures_of_control", []),
                "notified_on": item.get("notified_on", ""),
                "ceased_on": item.get("ceased_on"),
                "country_of_residence": item.get("country_of_residence", ""),
                "nationality": item.get("nationality", ""),
                "date_of_birth": item.get("date_of_birth"),
                "address": item.get("address", {}),
            })
        return psc_list
    except Exception as e:
        log.warning("CH PSC API error for %s: %s", company_number, e)
        return []
    finally:
        client.close()


def summarise_psc(psc_list: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise PSC data for a company."""
    if not psc_list:
        return {"count": 0}

    active = [p for p in psc_list if not p.get("ceased_on")]
    total_bands: dict[str, int] = {}
    for p in active:
        for noc in p.get("nature_of_control", []):
            if "ownership" in noc or "voting" in noc:
                total_bands[noc] = total_bands.get(noc, 0) + 1

    return {
        "count": len(active),
        "ceased": len(psc_list) - len(active),
        "control_types": total_bands,
        "has_corporate_controller": any(p.get("kind") == "corporate-entity-managing-jurisdition" for p in active),
    }
