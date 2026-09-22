"""US Congress Trading collector.

Fetches House and Senate financial disclosure trades.
Public government data — no API key required.

Reference: reference/insider-scanner/congress_house.py, congress_senate.py
"""

import logging
import re
import time
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

import httpx

log = logging.getLogger(__name__)

HOUSE_INDEX_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
SENATE_SEARCH_URL = "https://efdsearch.senate.gov/search/report/data/"
SENATE_HOME_URL = "https://efdsearch.senate.gov/search/home/"
SENATE_LANDING_URL = "https://efdsearch.senate.gov/search/"

MAX_RETRIES = 3
RETRY_DELAY = 2.0


@dataclass
class CongressTrade:
    member_name: str
    party: str
    chamber: str  # "House" or "Senate"
    ticker: str
    asset_name: str
    tx_type: str  # "Purchase", "Sale", "Exchange"
    tx_date: str
    amount_range: str  # "$1,001 - $15,000" etc.
    notification_date: str
    source_url: str = ""
    raw: dict = field(default_factory=dict)


# ── House of Representatives ──────────────────────────────────────


def fetch_house_index(year: int, client: httpx.Client) -> bytes | None:
    """Download House annual filing index ZIP."""
    url = HOUSE_INDEX_URL.format(year=year)
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(url)
            if resp.status_code == 200:
                return resp.content
            log.warning("House index HTTP %d for %d", resp.status_code, year)
        except Exception as e:
            log.warning("House index error for %d: %s", year, e)
        time.sleep(RETRY_DELAY * (2 ** attempt))
    return None


def parse_house_index(xml_bytes: bytes) -> list[dict]:
    """Parse House filing index XML."""
    entries = []
    try:
        root = ET.fromstring(xml_bytes)
        for member in root.findall(".//Member"):
            entries.append({
                "last": member.findtext("Last", ""),
                "first": member.findtext("First", ""),
                "suffix": member.findtext("Suffix", ""),
                "filing_type": member.findtext("FilingType", ""),
                "state_dst": member.findtext("StateDst", ""),
                "year": member.findtext("Year", ""),
                "filing_date": member.findtext("FilingDate", ""),
                "doc_id": member.findtext("DocID", ""),
            })
    except ET.ParseError as e:
        log.warning("House XML parse error: %s", e)
    return entries


def search_house_filings(
    year: int,
    client: httpx.Client,
    filing_type: str = "P",
) -> list[dict]:
    """Search House filings for a year. Returns PTR filings."""
    xml_bytes = fetch_house_index(year, client)
    if not xml_bytes:
        return []

    all_entries = parse_house_index(xml_bytes)
    return [e for e in all_entries if e.get("filing_type") == filing_type]


# ── Senate ────────────────────────────────────────────────────────


def _create_senate_session(client: httpx.Client) -> dict[str, str]:
    """Create authenticated Senate session with CSRF."""
    session_cookies = {}

    # Step 1: GET home page (CSRF is here, not on landing page)
    try:
        resp = client.get(SENATE_HOME_URL)
        csrf_match = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', resp.text)
        if not csrf_match:
            log.warning("Could not find CSRF token on Senate page")
            return {}

        csrf_token = csrf_match.group(1)
        session_cookies["csrftoken"] = csrf_token

        # Step 2: Accept prohibition agreement
        resp2 = client.post(
            SENATE_HOME_URL,
            data={
                "csrfmiddlewaretoken": csrf_token,
                "prohibition_agreement": "1",
            },
            headers={"Referer": SENATE_HOME_URL},
        )
    except Exception as e:
        log.warning("Senate session creation failed: %s", e)

    return session_cookies


def search_senate_filings(
    client: httpx.Client,
    last_name: str = "",
    first_name: str = "",
    start: int = 0,
    length: int = 100,
) -> list[dict]:
    """Search Senate EFD filings."""
    _create_senate_session(client)

    try:
        resp = client.post(
            SENATE_SEARCH_URL,
            data={
                "first_name": first_name,
                "last_name": last_name,
                "report_types[]": "11",  # PTR
                "filter_types[]": "1",   # Senator
                "start": start,
                "length": length,
            },
            headers={
                "Referer": "https://efdsearch.senate.gov/search/home/",
                "X-CSRFToken": client.cookies.get("csrftoken", ""),
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except Exception as e:
        log.warning("Senate search error: %s", e)
        return []


# ── Combined ──────────────────────────────────────────────────────


def fetch_congress_trades(
    year: int | None = None,
    client: httpx.Client | None = None,
) -> list[CongressTrade]:
    """Fetch recent Congress trading disclosures.

    Args:
        year: Year to fetch (default: current year).
        client: Optional httpx client.
    """
    if year is None:
        from datetime import datetime
        year = datetime.now().year

    should_close = client is None
    if client is None:
        client = httpx.Client(timeout=30, follow_redirects=True)

    trades = []

    try:
        # House filings
        house_filings = search_house_filings(year, client)
        log.info("House: %d PTR filings for %d", len(house_filings), year)

        for filing in house_filings[:100]:  # limit for rate limiting
            name = f"{filing['first']} {filing['last']}"
            trades.append(CongressTrade(
                member_name=name.strip(),
                party="",
                chamber="House",
                ticker="",
                asset_name="",
                tx_type="",
                tx_date=filing.get("filing_date", ""),
                amount_range="",
                notification_date=filing.get("filing_date", ""),
                source_url=f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{filing['doc_id']}.pdf",
                raw=filing,
            ))

        # Senate filings
        senate_data = search_senate_filings(client)
        log.info("Senate: %d filings", len(senate_data))

        for row in senate_data:
            if len(row) >= 5:
                trades.append(CongressTrade(
                    member_name=f"{row[0]} {row[1]}".strip(),
                    party="",
                    chamber="Senate",
                    ticker="",
                    asset_name="",
                    tx_type="",
                    tx_date=row[4] if len(row) > 4 else "",
                    amount_range="",
                    notification_date="",
                    source_url=row[3] if len(row) > 3 else "",
                    raw={"row": row},
                ))

    finally:
        if should_close:
            client.close()

    return trades


def filter_universe_congress_trades(
    trades: list[CongressTrade],
) -> list[CongressTrade]:
    """Filter Congress trades to those mentioning universe companies."""
    from powstock.universe import UNIVERSE

    search_terms = set()
    for security in UNIVERSE:
        search_terms.add(security.ticker.upper())
        search_terms.add(security.company.upper())

    return [
        t for t in trades
        if any(term in (t.ticker + t.asset_name).upper() for term in search_terms)
    ]
