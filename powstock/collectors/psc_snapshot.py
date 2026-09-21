"""Companies House PSC daily snapshot collector.

Downloads the daily PSC (Persons with Significant Control) bulk dataset.
This is a ZIP file containing JSON records of all PSCs in the UK.
Updated daily before 10am GMT.

URL: https://download.companieshouse.gov.uk/en_pscdata.html
"""

import json
import logging
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

CH_PSC_URL = "https://download.companieshouse.gov.uk/psc-snapshot-{date_str}.json.zip"
CH_PSC_HISTORIC_URL = "https://download.companieshouse.gov.uk/psc-snapshot-{date_str}.json.zip"


def _get_date_str(dt: datetime) -> str:
    """Format date as YYYY-MM-DD."""
    return dt.strftime("%Y-%m-%d")


def download_psc_snapshot(
    date: datetime | None = None,
    cache_dir: Path = Path("data/raw/psc"),
) -> dict[str, Any] | None:
    """Download and extract the daily PSC snapshot.

    Args:
        date: Date to fetch (default: yesterday).
        cache_dir: Directory to cache downloaded files.

    Returns:
        Dict with keys: records, requested_date, source_date, source_url, sha256.
        Or None if unavailable.
    """
    if date is None:
        date = datetime.now() - timedelta(days=1)

    requested_date_str = _get_date_str(date)
    cache_file = cache_dir / f"psc-snapshot-{requested_date_str}.json"

    # Check cache
    if cache_file.exists():
        import hashlib
        raw_bytes = cache_file.read_bytes()
        return {
            "records": json.loads(raw_bytes),
            "requested_date": requested_date_str,
            "source_date": requested_date_str,  # assumed same from cache
            "source_url": "",
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        }

    # Download — try requested date, then fall back to previous day
    import hashlib

    client = httpx.Client(timeout=60, follow_redirects=True)
    source_date = requested_date_str
    source_url = CH_PSC_URL.format(date_str=requested_date_str)

    try:
        resp = client.get(source_url)
        if resp.status_code == 404:
            # Try previous day
            prev_date = date - timedelta(days=1)
            source_date = _get_date_str(prev_date)
            source_url = CH_PSC_URL.format(date_str=source_date)
            resp = client.get(source_url)
            if resp.status_code == 404:
                return None

        resp.raise_for_status()

        # Extract ZIP
        with zipfile.ZipFile(BytesIO(resp.content)) as zf:
            json_files = [f for f in zf.namelist() if f.endswith(".json")]
            if not json_files:
                return None

            records = []
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

            # Cache — store under requested_date but record actual source_date
            cache_dir.mkdir(parents=True, exist_ok=True)
            raw_json = json.dumps(records)
            with open(cache_file, "w") as f:
                f.write(raw_json)

            return {
                "records": records,
                "requested_date": requested_date_str,
                "source_date": source_date,
                "source_url": source_url,
                "sha256": hashlib.sha256(raw_json.encode()).hexdigest(),
            }

    except Exception as e:
        log.warning("PSC snapshot download error: %s", e)
        return None
    finally:
        client.close()


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
            "psc_kind": psc.get("kind", ""),  # person-on-rol or corporate-entity
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


def fetch_psc_api_current(
    universe_tickers: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch current PSC data for universe companies via REST API.

    This hits the live Companies House PSC endpoints, NOT the bulk snapshot.
    Returns: {ticker: [psc_records]}
    """
    from powstock.universe import UNIVERSE

    if universe_tickers is None:
        universe_tickers = [s.ticker for s in UNIVERSE]

    # Get company numbers from Companies House
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


# Backwards compat alias
def fetch_universe_psc(
    universe_tickers: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Alias for fetch_psc_api_current — kept for backwards compatibility."""
    return fetch_psc_api_current(universe_tickers)


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
    except httpx.HTTPStatusError as e:
        log.warning("CH PSC API HTTP %s for %s: %s", e.response.status_code, company_number, e)
        return []
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
    total_bands = {}
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
