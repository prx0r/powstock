"""Companies House PSC daily snapshot collector.

Downloads the daily PSC (Persons with Significant Control) bulk dataset.
This is a ZIP file containing JSON records of all PSCs in the UK.
Updated daily before 10am GMT.

URL: https://download.companieshouse.gov.uk/en_pscdata.html
"""

import json
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx

CH_PSC_URL = "https://download.companieshouse.gov.uk/psc-snapshot-{date_str}.json.zip"
CH_PSC_HISTORIC_URL = "https://download.companieshouse.gov.uk/psc-snapshot-{date_str}.json.zip"


def _get_date_str(dt: datetime) -> str:
    """Format date as YYYY-MM-DD."""
    return dt.strftime("%Y-%m-%d")


def download_psc_snapshot(
    date: datetime | None = None,
    cache_dir: Path = Path("data/raw/psc"),
) -> list[dict[str, Any]] | None:
    """Download and extract the daily PSC snapshot.

    Args:
        date: Date to fetch (default: yesterday).
        cache_dir: Directory to cache downloaded files.

    Returns:
        List of PSC records, or None if unavailable.
    """
    if date is None:
        date = datetime.now() - timedelta(days=1)

    date_str = _get_date_str(date)
    cache_file = cache_dir / f"psc-snapshot-{date_str}.json"

    # Check cache
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    # Download
    url = CH_PSC_URL.format(date_str=date_str)
    client = httpx.Client(timeout=60, follow_redirects=True)

    try:
        resp = client.get(url)
        if resp.status_code == 404:
            # Try previous day
            prev_date = date - timedelta(days=1)
            url = CH_PSC_URL.format(date_str=_get_date_str(prev_date))
            resp = client.get(url)
            if resp.status_code == 404:
                return None

        resp.raise_for_status()

        # Extract ZIP
        with zipfile.ZipFile(BytesIO(resp.content)) as zf:
            # Find the JSON file inside
            json_files = [f for f in zf.namelist() if f.endswith(".json")]
            if not json_files:
                return None

            records = []
            for json_file in json_files:
                with zf.open(json_file) as jf:
                    # PSC snapshot is newline-delimited JSON
                    for line in jf:
                        line = line.strip()
                        if line:
                            try:
                                record = json.loads(line)
                                records.append(record)
                            except json.JSONDecodeError:
                                continue

            # Cache
            cache_dir.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "w") as f:
                json.dump(records, f)

            return records

    except Exception as e:
        print(f"  Error downloading PSC snapshot: {e}")
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
    except Exception:
        return {}


def fetch_universe_psc(
    universe_tickers: list[str] | None = None,
    days_back: int = 7,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch PSC data for universe companies.

    Returns: {ticker: [psc_records]}
    """
    from powstock.universe import BY_TICKER, UNIVERSE

    if universe_tickers is None:
        universe_tickers = [s.ticker for s in UNIVERSE]

    # Get company numbers from Companies House
    from powstock.collectors.companies_house import fetch_universe_companies
    companies = fetch_universe_companies()

    # Collect PSC data
    results: dict[str, list[dict[str, Any]]] = {}

    for ticker in universe_tickers:
        if ticker not in companies:
            continue

        company_number = companies[ticker].get("company_number", "")
        if not company_number:
            continue

        # Fetch PSC via REST API (not bulk)
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
    except Exception:
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
