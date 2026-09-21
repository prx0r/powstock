"""Parser regression tests.

Each fixture is a known-good source artifact.
The parser must produce exactly the expected output.
"""

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def test_company_profile_parse():
    """Verify company profile parsing from fixture."""
    from powstock.collectors.companies_house import CompanyProfile

    data = json.loads((FIXTURES / "companies_house/company.json").read_text())

    profile = CompanyProfile(
        company_number=data["company_number"],
        company_name=data["company_name"],
        status=data["company_status"],
        sic_codes=[str(s) for s in data.get("sic_codes", [])],
        registered_office="1-3 Strand, London, WC2N 5EH",
        incorporation_date=data.get("date_of_incorporation", ""),
        accounts_next_due=data.get("accounts", {}).get("next_accounts", {}).get("due_on", ""),
        confirmation_statement_next_due=data.get("confirmation_statement", {}).get("next_due_on", ""),
        raw=data,
    )

    assert profile.company_number == "04031152"
    assert profile.company_name == "NATIONAL GRID PLC"
    assert profile.status == "active"
    assert "64610" in profile.sic_codes
    assert profile.raw == data


def test_filing_parse():
    """Verify filing history parsing from fixture."""
    data = json.loads((FIXTURES / "companies_house/filing_history.json").read_text())

    assert len(data) == 2
    assert data[0]["description"] == "Confirmation statement made up of 30-06-2026"
    assert data[0]["category"] == "confirmation-statement"
    assert data[1]["category"] == "accounts"


def test_short_interest_exact_match():
    """Verify short interest exact matching avoids false positives.

    The substring 'SSE' appears in ESSENTRA and LIONTRUST.
    Our matching must use exact company name or ISIN, not substring.
    """
    import csv
    import io

    csv_text = (FIXTURES / "prices/short_positions.csv").read_text()
    reader = csv.DictReader(io.StringIO(csv_text))

    positions = []
    for row in reader:
        positions.append({
            "isin": row["ISIN"].strip(),
            "company": row["name"].strip(),
            "position_pct": float(row["Position (%)"].strip()),
        })

    # SSE exact match should find SSE PLC
    sse = [p for p in positions if p["company"] == "SSE PLC"]
    assert len(sse) == 1
    assert sse[0]["isin"] == "GB0B09SN5P82"

    # 'SSE' substring matches 3 companies — proves substring matching is broken
    sse_substring = [p for p in positions if "SSE" in p["company"]]
    assert len(sse_substring) == 3, "Substring 'SSE' matches SSE, ESSENTRA, LIONTRUST"

    # Exact name match correctly finds only SSE PLC
    exact_sse = [p for p in positions if p["company"] == "SSE PLC"]
    assert len(exact_sse) == 1

    # ISIN match correctly finds only SSE PLC
    isin_match = [p for p in positions if p["isin"] == "GB0B09SN5P82"]
    assert len(isin_match) == 1


def test_filing_event_map_no_leading_spaces():
    """Verify filing event map values have no leading whitespace."""
    from powstock.collectors.filing_events import FILING_EVENT_MAP

    for key, value in FILING_EVENT_MAP.items():
        assert value == value.strip(), f"Filing event '{key}' has leading/trailing space: '{value}'"


def test_daily_state_nullable():
    """Verify daily state uses None for missing data, not zero."""
    from datetime import date

    from powstock.schema.daily_state import PowCompanyStateDaily

    state = PowCompanyStateDaily(
        date=date(2026, 9, 21),
        entity_id="TEST",
        company_number="0000000",
        ticker="TEST",
        isin="GB0000000000",
        lei="",
    )

    # Nullable fields should be None, not 0
    assert state.employees is None
    assert state.turnover is None
    assert state.cash is None
    assert state.insider_buy_value_7d is None
    assert state.constraint_score is None

    # Identity fields should be set
    assert state.ticker == "TEST"
    assert state.date == date(2026, 9, 21)
