"""Companies House collector.

Uses the Companies House REST API for company profiles, officers, filings, and charges.
API key from powuk SDK. Free, 600 requests per 5 minutes.
"""

import base64
import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

CH_BASE = "https://api.company-information.service.gov.uk"
CH_API_KEY = "d284d51e"  # from powuk


@dataclass
class CompanyProfile:
    company_number: str
    company_name: str
    status: str
    sic_codes: list[str]
    registered_office: str
    incorporation_date: str
    accounts_next_due: str
    confirmation_statement_next_due: str
    source: str = "companies_house"
    raw: dict = field(default_factory=dict)


@dataclass
class Officer:
    name: str
    role: str
    appointed_date: str
    resigned_date: str | None
    nationality: str
    country_of_residence: str
    source: str = "companies_house"


@dataclass
class Filing:
    date: str
    description: str
    category: str
    document_id: str
    source: str = "companies_house"


def _get_auth() -> tuple[str, str]:
    """Return HTTP Basic auth tuple for Companies House API."""
    return (CH_API_KEY, "")


def fetch_company_profile(company_number: str) -> CompanyProfile | None:
    """Fetch full company profile from Companies House."""
    client = httpx.Client(timeout=30)
    try:
        resp = client.get(
            f"{CH_BASE}/company/{company_number}",
            auth=_get_auth(),
        )
        resp.raise_for_status()
        data = resp.json()

        return CompanyProfile(
            company_number=company_number,
            company_name=data.get("company_name", ""),
            status=data.get("company_status", ""),
            sic_codes=[str(s) for s in data.get("sic_codes", [])],
            registered_office=_format_address(data.get("registered_office_address", {})),
            incorporation_date=data.get("date_of_incorporation", ""),
            accounts_next_due=data.get("accounts", {}).get("next_accounts", {}).get("due_on", ""),
            confirmation_statement_next_due=data.get("confirmation_statement", {}).get("next_due_on", ""),
            raw=data,
        )
    except Exception:
        return None
    finally:
        client.close()


def fetch_company_officers(company_number: str) -> list[Officer]:
    """Fetch officers (directors, secretaries) for a company."""
    client = httpx.Client(timeout=30)
    try:
        resp = client.get(
            f"{CH_BASE}/company/{company_number}/officers",
            auth=_get_auth(),
            params={"items_per_page": 50},
        )
        resp.raise_for_status()
        data = resp.json()

        officers = []
        for item in data.get("items", []):
            officers.append(Officer(
                name=item.get("name", ""),
                role=item.get("officer_role", ""),
                appointed_date=item.get("appointed_on", ""),
                resigned_date=item.get("resigned_on"),
                nationality=item.get("nationality", ""),
                country_of_residence=item.get("country_of_residence", ""),
                raw=item,
            ))

        return officers
    except Exception:
        return []
    finally:
        client.close()


def fetch_company_filings(company_number: str) -> list[Filing]:
    """Fetch filing history for a company."""
    client = httpx.Client(timeout=30)
    try:
        resp = client.get(
            f"{CH_BASE}/company/{company_number}/filing-history",
            auth=_get_auth(),
            params={"items_per_page": 50},
        )
        resp.raise_for_status()
        data = resp.json()

        filings = []
        for item in data.get("items", []):
            filings.append(Filing(
                date=item.get("date", ""),
                description=item.get("description", ""),
                category=item.get("category", ""),
                document_id=item.get("document_id", ""),
                raw=item,
            ))

        return filings
    except Exception:
        return []
    finally:
        client.close()


def fetch_company_charges(company_number: str) -> list[dict[str, Any]]:
    """Fetch charges (mortgages/loans) for a company."""
    client = httpx.Client(timeout=30)
    try:
        resp = client.get(
            f"{CH_BASE}/company/{company_number}/charges",
            auth=_get_auth(),
            params={"items_per_page": 50},
        )
        resp.raise_for_status()
        data = resp.json()

        charges = []
        for item in data.get("items", []):
            charges.append({
                "charge_number": item.get("charge_number"),
                "created": item.get("created_on", ""),
                "satisfied": item.get("satisfied_on") is not None,
                "persons_entitled": [
                    p.get("name", "") for p in item.get("persons_entitled", [])
                ],
                "amount": item.get("amount", {}),
            })

        return charges
    except Exception:
        return []
    finally:
        client.close()


def fetch_company_psc(company_number: str) -> list[dict[str, Any]]:
    """Fetch persons with significant control for a company."""
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
                "nationality": item.get("nationality", ""),
                "nature_of_control": item.get("natures_of_control", []),
                "notified_on": item.get("notified_on", ""),
                "ceased_on": item.get("ceased_on"),
            })

        return psc_list
    except Exception:
        return []
    finally:
        client.close()


def fetch_officer_appointments(officer_id: str) -> list[dict[str, Any]]:
    """Fetch all company appointments for an officer."""
    client = httpx.Client(timeout=30)
    try:
        resp = client.get(
            f"{CH_BASE}/officers/{officer_id}/appointments",
            auth=_get_auth(),
        )
        resp.raise_for_status()
        data = resp.json()

        appointments = []
        for item in data.get("items", []):
            appointments.append({
                "company_name": item.get("company_name", ""),
                "company_number": item.get("company_number", ""),
                "officer_role": item.get("officer_role", ""),
                "appointed_on": item.get("appointed_on", ""),
                "resigned_on": item.get("resigned_on"),
            })

        return appointments
    except Exception:
        return []
    finally:
        client.close()


def _format_address(addr: dict) -> str:
    """Format address dict to string."""
    parts = [
        addr.get("address_line_1", ""),
        addr.get("address_line_2", ""),
        addr.get("locality", ""),
        addr.get("region", ""),
        addr.get("postal_code", ""),
    ]
    return ", ".join(p for p in parts if p)


def fetch_universe_companies() -> dict[str, dict[str, Any]]:
    """Fetch company data for all universe tickers.

    Returns: {ticker: {company_number, name, status, sic_codes, officers, ...}}
    """
    from powstock.universe import UNIVERSE

    results = {}

    for security in UNIVERSE:
        # Search for company by name
        client = httpx.Client(timeout=30)
        try:
            resp = client.get(
                f"{CH_BASE}/search/companies",
                auth=_get_auth(),
                params={"q": security.company, "items_per_page": 5},
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("items"):
                # Take the first match
                item = data["items"][0]
                company_number = item.get("company_number", "")

                # Fetch full profile
                profile = fetch_company_profile(company_number)
                officers = fetch_company_officers(company_number)
                charges = fetch_company_charges(company_number)
                psc = fetch_company_psc(company_number)

                results[security.ticker] = {
                    "ticker": security.ticker,
                    "company_number": company_number,
                    "company_name": item.get("title", ""),
                    "status": item.get("company_status", ""),
                    "sic_codes": profile.sic_codes if profile else [],
                    "registered_office": profile.registered_office if profile else "",
                    "incorporation_date": profile.incorporation_date if profile else "",
                    "accounts_next_due": profile.accounts_next_due if profile else "",
                    "officers_count": len(officers),
                    "charges_count": len(charges),
                    "active_charges": sum(1 for c in charges if not c.get("satisfied")),
                    "psc_count": len(psc),
                }

                time.sleep(0.2)  # rate limiting

        except Exception:
            continue
        finally:
            client.close()

        time.sleep(0.5)

    return results
