"""Entity resolver — links people across companies.

Builds a director/person graph from Companies House data.
When a director appears in multiple companies, we link them.
This creates the "who knows what through which companies" network.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class Person:
    person_id: str  # Companies House person_number (preferred) or name hash
    name: str
    title: str = ""
    forenames: str = ""
    surname: str = ""
    honours: str = ""
    date_of_birth: str = ""
    partial_dob: str = ""
    postcode: str = ""
    address: str = ""
    occupation: str = ""
    nationality: str = ""
    country_of_residence: str = ""
    corporate_indicator: bool = False
    roles: list[dict[str, Any]] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)
    is_disqualified: bool = False
    disqualifications: list[dict[str, Any]] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""
    source: str = "api"


@dataclass
class Company:
    company_number: str
    company_name: str
    officers: list[dict[str, Any]] = field(default_factory=list)
    pscs: list[dict[str, Any]] = field(default_factory=list)
    sector: str = ""
    pow_domains: list[str] = field(default_factory=list)


class EntityResolver:
    """Resolves entities across Companies House data."""

    def __init__(self):
        self.persons: dict[str, Person] = {}
        self.companies: dict[str, Company] = {}

    def add_company(self, company_number: str, company_name: str) -> Company:
        """Add or update a company."""
        if company_number not in self.companies:
            self.companies[company_number] = Company(
                company_number=company_number,
                company_name=company_name,
            )
        return self.companies[company_number]

    def add_officer(
        self,
        company_number: str,
        officer_name: str,
        role: str,
        appointed_date: str = "",
        resigned_date: str = "",
        officer_id: str = "",
    ) -> Person:
        """Add an officer and link to company."""
        # Create person ID from name (or use officer_id if available)
        person_id = officer_id or self._name_to_id(officer_name)

        if person_id not in self.persons:
            self.persons[person_id] = Person(
                person_id=person_id,
                name=officer_name,
            )

        person = self.persons[person_id]
        person.roles.append({
            "company_number": company_number,
            "role": role,
            "appointed_date": appointed_date,
            "resigned_date": resigned_date,
        })

        if company_number not in person.companies:
            person.companies.append(company_number)

        # Update company
        company = self.add_company(company_number, "")
        company.officers.append({
            "name": officer_name,
            "role": role,
            "appointed_date": appointed_date,
            "resigned_date": resigned_date,
            "person_id": person_id,
        })

        return person

    def add_psc(
        self,
        company_number: str,
        psc_name: str,
        nature_of_control: list[str],
        notified_on: str = "",
    ) -> None:
        """Add a PSC and link to company."""
        company = self.add_company(company_number, "")
        company.pscs.append({
            "name": psc_name,
            "nature_of_control": nature_of_control,
            "notified_on": notified_on,
        })

    def get_person_companies(self, person_id: str) -> list[str]:
        """Get all companies a person is associated with."""
        if person_id in self.persons:
            return self.persons[person_id].companies
        return []

    def get_company_officers(self, company_number: str) -> list[dict[str, Any]]:
        """Get all officers of a company."""
        if company_number in self.companies:
            return self.companies[company_number].officers
        return []

    def find_shared_directors(self, company_a: str, company_b: str) -> list[str]:
        """Find directors that sit on both company boards."""
        officers_a = {o["name"] for o in self.get_company_officers(company_a)}
        officers_b = {o["name"] for o in self.get_company_officers(company_b)}
        return list(officers_a & officers_b)

    def get_director_network(self, person_id: str, depth: int = 2) -> dict[str, Any]:
        """Get the network of companies and people around a person.

        Returns:
            {
                "person": Person,
                "direct_companies": [...],
                "connected_persons": [...],
                "connected_companies": [...],
            }
        """
        if person_id not in self.persons:
            return {}

        person = self.persons[person_id]
        connected_persons = set()
        connected_companies = set(person.companies)

        # Find people connected through shared companies
        for company_number in person.companies:
            for officer in self.get_company_officers(company_number):
                if officer.get("person_id") != person_id:
                    connected_persons.add(officer["person_id"])
                    # Their companies
                    if officer["person_id"] in self.persons:
                        for c in self.persons[officer["person_id"]].companies:
                            connected_companies.add(c)

        return {
            "person": person,
            "direct_companies": person.companies,
            "connected_persons": list(connected_persons),
            "connected_companies": list(connected_companies),
        }

    def resolve_universe(self, universe_tickers: list[str] | None = None) -> None:
        """Resolve all companies in the universe."""
        from powstock.universe import UNIVERSE
        from powstock.collectors.companies_house import fetch_company_profile, fetch_company_officers

        if universe_tickers is None:
            universe_tickers = [s.ticker for s in UNIVERSE]

        for security in UNIVERSE:
            if security.ticker not in universe_tickers:
                continue

            # Search for company
            from powstock.collectors.companies_house import CH_BASE, _get_auth

            client = httpx.Client(timeout=30)
            try:
                resp = client.get(
                    f"{CH_BASE}/search/companies",
                    auth=_get_auth(),
                    params={"q": security.company, "items_per_page": 1},
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("items"):
                    item = data["items"][0]
                    company_number = item.get("company_number", "")
                    company_name = item.get("title", "")

                    company = self.add_company(company_number, company_name)
                    company.sector = security.exchange
                    company.pow_domains = security.pow_layers

                    # Fetch officers
                    officers = fetch_company_officers(company_number)
                    for officer in officers:
                        self.add_officer(
                            company_number=company_number,
                            officer_name=officer.name,
                            role=officer.role,
                            appointed_date=officer.appointed_date,
                            resigned_date=officer.resigned_date or "",
                        )

            except Exception as e:
                log.warning("Resolver error for %s: %s", security.company, e)
            finally:
                client.close()

    def _name_to_id(self, name: str) -> str:
        """Convert name to consistent ID."""
        import hashlib
        normalized = name.upper().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def export_graph(self) -> dict[str, Any]:
        """Export the entity graph as a dictionary."""
        return {
            "persons": {k: {
                "name": v.name,
                "companies": v.companies,
                "roles": v.roles,
            } for k, v in self.persons.items()},
            "companies": {k: {
                "name": v.company_name,
                "officers": [o["name"] for o in v.officers],
                "pow_domains": v.pow_domains,
            } for k, v in self.companies.items()},
            "stats": {
                "persons": len(self.persons),
                "companies": len(self.companies),
                "multi_company_persons": sum(1 for p in self.persons.values() if len(p.companies) > 1),
            },
        }
