"""Financial extraction collector using stream-read-xbrl.

Uses the official UK government tool to parse Companies House bulk XBRL accounts.
Produces 38 columns of normalised financial data per company.

Reference: /root/powstock/reference/stream-read-xbrl
"""

from datetime import datetime, date
from pathlib import Path
from typing import Any

import httpx


# The 38 columns from stream-read-xbrl
FINANCIAL_COLUMNS = [
    "run_code", "company_id", "date", "file_type", "taxonomy",
    "balance_sheet_date", "companies_house_registered_number",
    "entity_current_legal_name", "company_dormant",
    "average_number_employees_during_period", "period_start", "period_end",
    "tangible_fixed_assets", "debtors", "cash_bank_in_hand", "current_assets",
    "creditors_due_within_one_year", "creditors_due_after_one_year",
    "net_current_assets_liabilities", "total_assets_less_current_liabilities",
    "net_assets_liabilities_including_pension_asset_liability",
    "called_up_share_capital", "profit_loss_account_reserve",
    "shareholder_funds", "turnover_gross_operating_revenue",
    "other_operating_income", "cost_sales", "gross_profit_loss",
    "administrative_expenses", "raw_materials_consumables", "staff_costs",
    "depreciation_other_amounts_written_off_tangible_intangible_fixed_assets",
    "other_operating_charges_format2", "operating_profit_loss",
    "profit_loss_on_ordinary_activities_before_tax",
    "tax_on_profit_or_loss_on_ordinary_activities", "profit_loss_for_period",
    "error", "zip_url",
]

# Key financial fields for powstock
KEY_FIELDS = [
    "company_id",
    "entity_current_legal_name",
    "balance_sheet_date",
    "period_start",
    "period_end",
    "turnover_gross_operating_revenue",
    "gross_profit_loss",
    "operating_profit_loss",
    "profit_loss_on_ordinary_activities_before_tax",
    "profit_loss_for_period",
    "tangible_fixed_assets",
    "current_assets",
    "cash_bank_in_hand",
    "creditors_due_within_one_year",
    "creditors_due_after_one_year",
    "net_current_assets_liabilities",
    "total_assets_less_current_liabilities",
    "shareholder_funds",
    "called_up_share_capital",
    "average_number_employees_during_period",
    "staff_costs",
    "taxonomy",
]


def fetch_single_zip(
    zip_url: str,
) -> list[dict[str, Any]]:
    """Parse a single Companies House XBRL ZIP file.

    Returns list of dicts with 38 columns.
    """
    try:
        from stream_read_xbrl import stream_read_xbrl_zip
    except ImportError:
        print("stream-read-xbrl not installed. Run: pip install stream-read-xbrl")
        return []

    client = httpx.Client(timeout=60, follow_redirects=True)
    try:
        with client.stream("GET", zip_url) as resp:
            resp.raise_for_status()

            with stream_read_xbrl_zip(
                resp.iter_bytes(chunk_size=100 * 1048576),
                zip_url=zip_url,
            ) as (columns, rows):
                results = []
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    # Skip rows with errors
                    if row_dict.get("error"):
                        continue
                    results.append(row_dict)

                return results

    except Exception as e:
        print(f"Error parsing {zip_url}: {e}")
        return []
    finally:
        client.close()


def fetch_latest_accounts(
    after_date: date | None = None,
) -> list[dict[str, Any]]:
    """Fetch and parse the latest Companies House accounts data.

    Uses stream_read_xbrl_sync to auto-discover ZIP URLs.
    Returns list of normalised financial records.
    """
    try:
        from stream_read_xbrl import stream_read_xbrl_sync
    except ImportError:
        print("stream-read-xbrl not installed. Run: pip install stream-read-xbrl")
        return []

    if after_date is None:
        after_date = date.today()

    results = []
    try:
        with stream_read_xbrl_sync(
            ingest_data_after_date=after_date,
        ) as (columns, date_range_and_rows):
            for (start_date, end_date), rows in date_range_and_rows:
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    if row_dict.get("error"):
                        continue
                    results.append(row_dict)

    except Exception as e:
        print(f"Error in stream_read_xbrl_sync: {e}")

    return results


def filter_universe_financials(
    records: list[dict[str, Any]],
    universe_tickers: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Filter financial records to universe companies.

    Returns: {ticker: latest_financials}
    """
    from powstock.universe import BY_TICKER, UNIVERSE

    if universe_tickers is None:
        universe_tickers = [s.ticker for s in UNIVERSE]

    # Build company number lookup from universe
    # (we need to map company names/numbers to tickers)
    company_to_ticker: dict[str, str] = {}

    # For now, match by company name similarity
    for security in UNIVERSE:
        company_to_ticker[security.company.upper()] = security.ticker

    results: dict[str, dict[str, Any]] = {}

    for record in records:
        company_name = (record.get("entity_current_legal_name") or "").upper()
        company_id = record.get("company_id") or record.get("companies_house_registered_number") or ""

        # Try matching by name
        for security in UNIVERSE:
            if security.company.upper() in company_name or company_name in security.company.upper():
                ticker = security.ticker
                # Keep latest record per ticker
                if ticker not in results or record.get("balance_sheet_date") > results[ticker].get("balance_sheet_date"):
                    results[ticker] = record
                break

    return results


def summarise_financials(record: dict[str, Any]) -> dict[str, Any]:
    """Summarise financial record for signal construction."""
    turnover = record.get("turnover_gross_operating_revenue")
    operating_profit = record.get("operating_profit_loss")
    cash = record.get("cash_bank_in_hand")
    current_assets = record.get("current_assets")
    creditors_1y = record.get("creditors_due_within_one_year")
    employees = record.get("average_number_employees_during_period")

    # Compute derived metrics
    gross_margin = None
    operating_margin = None
    current_ratio = None
    revenue_per_employee = None

    if turnover and turnover > 0:
        if operating_profit:
            gross_margin = float(operating_profit) / float(turnover)
        if employees and employees > 0:
            revenue_per_employee = float(turnover) / float(employees)

    if current_assets and creditors_1y and creditors_1y > 0:
        current_ratio = float(current_assets) / float(creditors_1y)

    return {
        "company_id": record.get("company_id"),
        "company_name": record.get("entity_current_legal_name"),
        "balance_sheet_date": str(record.get("balance_sheet_date", "")),
        "turnover": float(turnover) if turnover else None,
        "operating_profit": float(operating_profit) if operating_profit else None,
        "cash": float(cash) if cash else None,
        "current_assets": float(current_assets) if current_assets else None,
        "employees": float(employees) if employees else None,
        "gross_margin": round(gross_margin, 4) if gross_margin else None,
        "operating_margin": round(operating_margin, 4) if operating_margin else None,
        "current_ratio": round(current_ratio, 2) if current_ratio else None,
        "revenue_per_employee": round(revenue_per_employee, 0) if revenue_per_employee else None,
        "taxonomy": record.get("taxonomy", ""),
    }
