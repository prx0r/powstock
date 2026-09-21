"""UK Parliament MP Financial Interests collector.

Fetches MP shareholdings and financial interests from the UK Parliament API.
Open Parliament Licence v3.0 — no API key required.

API: https://members-api.parliament.uk/api/
Reference: reference/uk-parliament-interests-tracker/
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger(__name__)

MEMBERS_API = "https://members-api.parliament.uk/api/Members/Search"
INTERESTS_API = "https://members-api.parliament.uk/api/Members/{member_id}/RegisteredInterests"
TAKE = 20
MAX_RETRIES = 3
RETRY_DELAY = 1.0
MP_FETCH_TIMEOUT = 5  # seconds per MP interest fetch


@dataclass
class MPShareholding:
    member_id: int
    member_name: str
    party: str
    category: str  # "Shareholdings" etc.
    description: str
    registered_at: str
    raw: dict = field(default_factory=dict)


def _fetch_with_retry(client: httpx.Client, url: str, params: dict | None = None) -> dict | None:
    """Fetch with retry on 429/5xx."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(url, params=params, timeout=10)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", RETRY_DELAY * (2 ** attempt)))
                time.sleep(min(retry_after, 10))
                continue
            if resp.status_code >= 500:
                time.sleep(RETRY_DELAY * (2 ** attempt))
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            log.warning("HTTP %s on attempt %d for %s: %s", e.response.status_code, attempt + 1, url, e)
            time.sleep(RETRY_DELAY * (2 ** attempt))
        except Exception as e:
            log.warning("Error on attempt %d for %s: %s", attempt + 1, url, e)
            time.sleep(RETRY_DELAY * (2 ** attempt))
    return None


def fetch_mp_members(client: httpx.Client | None = None) -> list[dict]:
    """Fetch all current MP member IDs and names (House of Commons only)."""
    should_close = client is None
    if client is None:
        client = httpx.Client(timeout=30, follow_redirects=True)

    members = []
    skip = 0

    try:
        while True:
            data = _fetch_with_retry(client, MEMBERS_API, params={"skip": skip, "take": TAKE})
            if not data or "items" not in data:
                break

            for item in data["items"]:
                value = item.get("value", {})
                house_membership = value.get("latestHouseMembership", {})
                # house=1 is Commons, end=None means still serving
                if house_membership.get("house") == 1 and not house_membership.get("end"):
                    members.append({
                        "member_id": value.get("id"),
                        "name": value.get("nameDisplayAs", ""),
                        "party": value.get("latestParty", {}).get("name", ""),
                        "house": "Commons",
                    })

            total = data.get("totalResults", 0)
            skip += TAKE
            if skip >= total:
                break

            time.sleep(0.2)
    finally:
        if should_close:
            client.close()

    return members


def fetch_mp_interests(member_id: int, client: httpx.Client) -> list[dict]:
    """Fetch registered interests for a single MP."""
    url = INTERESTS_API.format(member_id=member_id)
    data = _fetch_with_retry(client, url)
    if not data:
        return []

    interests = []
    for category in data.get("value", []):
        cat_name = category.get("name", "")  # e.g. "3. Shareholdings"
        for item in category.get("interests", []):
            # Include child interests (amendments, details)
            all_interests = [item] + item.get("childInterests", [])
            for interest in all_interests:
                interests.append({
                    "category": cat_name,
                    "description": interest.get("interest", ""),
                    "registered_at": interest.get("createdWhen", ""),
                    "last_amended": interest.get("lastAmendedWhen", ""),
                })

    return interests


def extract_shareholdings(interests: list[dict]) -> list[dict]:
    """Extract shareholding entries from interests list."""
    shareholdings = []
    for interest in interests:
        cat = interest.get("category", "").lower()
        if "shareholding" in cat or "share" in cat:
            shareholdings.append(interest)
    return shareholdings


def fetch_all_mp_shareholdings(
    client: httpx.Client | None = None,
    max_mps: int = 5,
) -> list[MPShareholding]:
    """Fetch shareholdings for MPs.

    Args:
        max_mps: Maximum MPs to scan (default 50 for speed; set to -1 for all).
    """
    should_close = client is None
    if client is None:
        client = httpx.Client(timeout=30, follow_redirects=True)

    all_holdings = []

    try:
        members = fetch_mp_members(client)
        if max_mps > 0:
            members = members[:max_mps]
        log.info("Scanning %d MPs for shareholdings", len(members))

        for i, member in enumerate(members):
            member_id = member["member_id"]
            if not member_id:
                continue

            interests = fetch_mp_interests(member_id, client)
            shareholdings = extract_shareholdings(interests)

            for sh in shareholdings:
                all_holdings.append(MPShareholding(
                    member_id=member_id,
                    member_name=member["name"],
                    party=member["party"],
                    category=sh.get("category", "Shareholdings"),
                    description=sh.get("description", ""),
                    registered_at=sh.get("registered_at", ""),
                    raw=sh,
                ))

            if (i + 1) % 50 == 0:
                log.info("Fetched interests for %d/%d MPs", i + 1, len(members))

            time.sleep(0.05)
    finally:
        if should_close:
            client.close()

    return all_holdings


def filter_universe_holdings(
    holdings: list[MPShareholding],
    universe_tickers: list[str] | None = None,
) -> list[MPShareholding]:
    """Filter shareholdings to those mentioning universe companies.

    Searches description text for ticker symbols and company names.
    """
    if universe_tickers is None:
        from powstock.universe import UNIVERSE
        universe_tickers = [s.ticker for s in UNIVERSE]

    # Build search terms: tickers + company names
    from powstock.universe import UNIVERSE
    search_terms = set()
    for security in UNIVERSE:
        search_terms.add(security.ticker.upper())
        search_terms.add(security.company.upper())

    filtered = []
    for holding in holdings:
        desc_upper = holding.description.upper()
        if any(term in desc_upper for term in search_terms):
            filtered.append(holding)

    return filtered
