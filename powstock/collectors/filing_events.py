"""Companies House filing events collector.

Treats every filing as an economic event, not just metadata.
Classifies filings into corporate events:
- SH01 → share_issuance
- PSC01 → new_controller
- PSC07 → controller_ceased
- AP01 → director_appointed
- TM01 → director_departed
- MR01 → new_charge
- CS01 → ownership_snapshot
- AA → accounts_filed
"""

from datetime import datetime
from typing import Any

import httpx

# Filing type → event classification
FILING_EVENT_MAP = {
    "SH01": "share_issuance",
    "SH02": "share_subdivision",
    "SH03": "share_reduction",
    "SH04": "share_transfer",
    "PSC01": "new_controller",
    "PSC02": "controller_details_changed",
    "PSC03": "controller.notify_type_changed",
    "PSC04": "controller_details_changed",
    "PSC05": "controller_details_changed",
    "PSC06": "controller_details_changed",
    "PSC07": "controller_ceased",
    "PSC08": "controller.cessation_details",
    "AP01": "director_appointed",
    "AP02": "secretary_appointed",
    "TM01": "director_departed",
    "TM02": "secretary_departed",
    "TM03": "director_resigned",
    "MR01": "new_charge",
    "MR02": "charge_satisfied",
    "MR03": "charge_part_satisfied",
    "MR04": "charge_satisfied",
    "MR05": "charge_details_changed",
    "CS01": "ownership_snapshot",
    "AA": "accounts_filed",
    "AD01": "registered_address_changed",
    "AD02": "principal_office_changed",
    "DS01": "strike_off_attempted",
    "DS02": "strike_off_withdrawn",
    "GAZ1": "gazette_notice",
    "GAZ2": "gazette_second_notice",
    "LIQ01": "liquidator_appointed",
    "LIQ02": "liquidator_ceased",
    "LIQ03": "winding_up_petition",
    "LIQ04": "winding_up_order",
    "LIQ05": "creditors_meeting",
    "LIQ06": "final_meeting",
    "LIQ07": "dissolved",
    "RT01": "mortgage_satisfaction",
    "IP01": "insolvency_practitioner",
    "IP02": "administrative_receiver",
}

# Event severity weights
EVENT_WEIGHTS = {
    "new_controller": 0.9,
    "controller_ceased": 0.8,
    "share_issuance": 0.7,
    "new_charge": 0.6,
    "director_appointed": 0.5,
    "director_departed": 0.4,
    "liquidator_appointed": 0.95,
    "winding_up_petition": 0.99,
    "strike_off_attempted": 0.85,
}


def classify_filing(filing_type: str) -> dict[str, Any]:
    """Classify a Companies House filing type into an event.

    Returns:
        {
            "event_type": str,
            "category": str,
            "severity": float,
            "description": str,
        }
    """
    event_type = FILING_EVENT_MAP.get(filing_type, "unknown")

    # Determine category
    if filing_type.startswith("PSC"):
        category = "ownership"
    elif filing_type.startswith(("SH", "SD")):
        category = "capital"
    elif filing_type.startswith(("AP", "TM")):
        category = "directors"
    elif filing_type.startswith("MR"):
        category = "charges"
    elif filing_type.startswith("CS"):
        category = "ownership"
    elif filing_type.startswith("AA"):
        category = "financials"
    elif filing_type.startswith(("LIQ", "IP")):
        category = "insolvency"
    elif filing_type.startswith(("DS", "GAZ")):
        category = "dissolution"
    else:
        category = "other"

    severity = EVENT_WEIGHTS.get(event_type, 0.1)

    # Generate description
    descriptions = {
        "share_issuance": "New shares issued (dilution or capital raise)",
        "share_subdivision": "Shares subdivided/consolidated",
        "new_controller": "New person with significant control",
        "controller_ceased": "PSC ceased to have control",
        "controller_details_changed": "PSC details changed",
        "director_appointed": "New director appointed",
        "director_departed": "Director departed",
        "new_charge": "New charge/mortgage registered",
        "charge_satisfied": "Charge satisfied",
        "ownership_snapshot": "Confirmation statement filed",
        "accounts_filed": "Annual accounts filed",
        "strike_off_attempted": "Strike-off proceedings initiated",
        "liquidator_appointed": "Liquidator appointed",
        "winding_up_petition": "Winding-up petition filed",
    }

    return {
        "event_type": event_type,
        "category": category,
        "severity": severity,
        "description": descriptions.get(event_type, f"Filing: {filing_type}"),
    }


def fetch_company_events(
    company_number: str,
    max_results: int = 100,
) -> list[dict[str, Any]]:
    """Fetch and classify filing history for a company.

    Returns list of classified events with economic interpretation.
    """
    from powstock.collectors.companies_house import CH_BASE, _get_auth

    client = httpx.Client(timeout=30)
    try:
        resp = client.get(
            f"{CH_BASE}/company/{company_number}/filing-history",
            auth=_get_auth(),
            params={"items_per_page": max_results},
        )
        resp.raise_for_status()
        data = resp.json()

        events = []
        for item in data.get("items", []):
            filing_type = item.get("type", "")
            classification = classify_filing(filing_type)

            events.append({
                "company_number": company_number,
                "filing_type": filing_type,
                "filing_date": item.get("date", ""),
                "description": item.get("description", ""),
                "event_type": classification["event_type"],
                "category": classification["category"],
                "severity": classification["severity"],
                "event_description": classification["description"],
                "document_id": item.get("document_id", ""),
            })

        return events

    except Exception:
        return []
    finally:
        client.close()


def fetch_universe_events(
    max_results_per_company: int = 50,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch recent filing events for all universe companies.

    Returns: {ticker: [events]}
    """
    from powstock.collectors.companies_house import fetch_universe_companies

    companies = fetch_universe_companies()
    results: dict[str, list[dict[str, Any]]] = {}

    for ticker, data in companies.items():
        company_number = data.get("company_number", "")
        if not company_number:
            continue

        events = fetch_company_events(company_number, max_results_per_company)
        if events:
            results[ticker] = events

    return results


def summarise_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise filing events for signal construction."""
    if not events:
        return {"total": 0}

    # Count by category
    categories = {}
    for e in events:
        cat = e.get("category", "other")
        categories[cat] = categories.get(cat, 0) + 1

    # High-severity events
    high_severity = [e for e in events if e.get("severity", 0) >= 0.7]

    # Capital events
    capital_events = [e for e in events if e.get("category") == "capital"]

    # Ownership events
    ownership_events = [e for e in events if e.get("category") == "ownership"]

    # Director events
    director_events = [e for e in events if e.get("category") == "directors"]

    # Charges
    charge_events = [e for e in events if e.get("category") == "charges"]

    return {
        "total": len(events),
        "categories": categories,
        "high_severity_count": len(high_severity),
        "high_severity_types": [e["event_type"] for e in high_severity],
        "capital_events_count": len(capital_events),
        "ownership_events_count": len(ownership_events),
        "director_events_count": len(director_events),
        "charges_count": len(charge_events),
        "latest_event": events[0] if events else None,
    }
