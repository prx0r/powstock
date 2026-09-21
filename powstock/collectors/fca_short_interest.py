"""FCA short interest (ANSP) collector.

Downloads the daily aggregated net short position report from FCA.
Free, no API key. XLSX format (CSV no longer available).
"""

import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

log = logging.getLogger(__name__)

# FCA changed from CSV to XLSX format
FCA_ANSP_URL = "https://www.fca.org.uk/publication/documents/aggregated-net-short-positions.xlsx"
FCA_ANSP_HISTORIC_URL = "https://www.fca.org.uk/publication/documents/aggregated-historic-net-short-positions.csv"


@dataclass
class ShortPosition:
    isin: str
    issuer_name: str
    position_pct: float
    notional_value_gbp: float
    report_date: str
    source: str = "fca_ansp"


def fetch_current_short_positions() -> tuple[list[ShortPosition], bytes | None]:
    """Download the current aggregated net short positions from FCA.

    Returns (positions, raw_bytes). Raw bytes are the original XLSX/CSV.
    """
    client = httpx.Client(timeout=30)
    try:
        resp = client.get(FCA_ANSP_URL)
        resp.raise_for_status()
        raw_bytes = resp.content

        # Try to parse as XLSX first
        if resp.headers.get("content-type", "").startswith("application/vnd.openxmlformats"):
            try:
                import openpyxl
                import io

                wb = openpyxl.load_workbook(io.BytesIO(raw_bytes))
                ws = wb.active

                # Find header row (contains "ISIN" or "Name of Company")
                header_row = None
                for i, row in enumerate(ws.iter_rows(max_row=10, values_only=True)):
                    row_str = " ".join(str(c) for c in row if c)
                    if "ISIN" in row_str.upper() or "NAME OF COMPANY" in row_str.upper():
                        header_row = i
                        break

                if header_row is None:
                    return [], raw_bytes

                # Data starts 2 rows after header (skip empty row)
                data_start = header_row + 2
                positions = []

                for row in ws.iter_rows(min_row=data_start, values_only=True):
                    try:
                        # Expected columns: Name, ISIN, Position %, Date
                        if not row[0] or not row[1]:
                            continue

                        name = str(row[0]).strip()
                        isin = str(row[1]).strip()
                        
                        # Position percentage
                        pct = 0.0
                        if len(row) > 2:
                            if isinstance(row[2], (int, float)):
                                pct = float(row[2])
                            elif row[2]:
                                pct = float(str(row[2]).replace("%", "").replace(",", ""))

                        if not isin or isin == "None":
                            continue

                        positions.append(ShortPosition(
                            isin=isin,
                            issuer_name=name,
                            position_pct=pct,
                            notional_value_gbp=0.0,  # Not in this file format
                            report_date=datetime.now().strftime("%Y-%m-%d"),
                        ))
                    except (ValueError, KeyError, TypeError, IndexError):
                        continue

                return positions, raw_bytes

            except ImportError:
                pass  # Fall back to CSV parsing

        # Fallback: try CSV format (historic data)
        reader = csv.DictReader(io.StringIO(resp.text))
        positions = []

        for row in reader:
            try:
                isin = row.get("ISIN", "").strip()
                issuer = row.get("Issuer Name", row.get("Issuer", "")).strip()
                pct_str = row.get("Position (%)", row.get("Position", "0")).strip()
                notional_str = row.get("Notional Value (£)", row.get("Notional Value", "0")).strip()

                if not isin:
                    continue

                positions.append(ShortPosition(
                    isin=isin,
                    issuer_name=issuer,
                    position_pct=float(pct_str.replace("%", "").replace(",", "")),
                    notional_value_gbp=float(notional_str.replace("£", "").replace(",", "")),
                    report_date=datetime.now().strftime("%Y-%m-%d"),
                ))
            except (ValueError, KeyError):
                continue

        return positions, raw_bytes

    finally:
        client.close()


def fetch_historic_short_positions() -> list[ShortPosition]:
    """Download the historic aggregated net short positions CSV from FCA.

    Contains historical daily snapshots. Larger file.
    """
    client = httpx.Client(timeout=60)
    try:
        resp = client.get(FCA_ANSP_HISTORIC_URL)
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        positions = []

        for row in reader:
            try:
                isin = row.get("ISIN", "").strip()
                issuer = row.get("Issuer Name", row.get("Issuer", "")).strip()
                pct_str = row.get("Position (%)", row.get("Position", "0")).strip()
                notional_str = row.get("Notional Value (£)", row.get("Notional Value", "0")).strip()
                date_str = row.get("Date", row.get("Report Date", "")).strip()

                if not isin:
                    continue

                positions.append(ShortPosition(
                    isin=isin,
                    issuer_name=issuer,
                    position_pct=float(pct_str.replace("%", "").replace(",", "")),
                    notional_value_gbp=float(notional_str.replace("£", "").replace(",", "")),
                    report_date=date_str,
                ))
            except (ValueError, KeyError):
                continue

        return positions

    finally:
        client.close()


def lookup_ticker_short(
    ticker: str,
    positions: list[ShortPosition] | None = None,
) -> dict[str, Any] | None:
    """Look up short interest for a specific ticker.

    Note: FCA uses ISIN, not tickers. We need a ticker→ISIN mapping.
    For now, searches by issuer name containing the ticker company name.
    """
    if positions is None:
        positions, _raw_bytes = fetch_current_short_positions()

    # Try exact ISIN match first (if ticker is actually an ISIN)
    for pos in positions:
        if pos.isin.upper() == ticker.upper():
            return {
                "ticker": ticker,
                "isin": pos.isin,
                "company": pos.issuer_name,
                "short_pct": pos.position_pct,
                "notional_gbp": pos.notional_value_gbp,
                "report_date": pos.report_date,
                "source": pos.source,
            }

    # Fall back to name search
    ticker_upper = ticker.upper()
    for pos in positions:
        if ticker_upper in pos.issuer_name.upper():
            return {
                "ticker": ticker,
                "isin": pos.isin,
                "company": pos.issuer_name,
                "short_pct": pos.position_pct,
                "notional_gbp": pos.notional_value_gbp,
                "report_date": pos.report_date,
                "source": pos.source,
            }

    return None


def fetch_all_short_interest() -> dict[str, dict[str, Any]]:
    """Fetch short interest for all universe tickers.

    Returns: {ticker: {short_pct, notional_gbp, ...}}
    """
    from powstock.universe import UNIVERSE

    positions, _raw_bytes = fetch_current_short_positions()
    results = {}

    for security in UNIVERSE:
        # Try ISIN match first (exact)
        if security.isin:
            for pos in positions:
                if security.isin.upper() == pos.isin.upper():
                    results[security.ticker] = {
                        "ticker": security.ticker,
                        "isin": pos.isin,
                        "company": pos.issuer_name,
                        "short_pct": pos.position_pct,
                        "notional_gbp": pos.notional_value_gbp,
                        "report_date": pos.report_date,
                        "source": pos.source,
                    }
                    break

        # Try exact company name match (not substring)
        if security.ticker not in results:
            company_upper = security.company.upper()
            for pos in positions:
                if company_upper == pos.issuer_name.upper():
                    results[security.ticker] = {
                        "ticker": security.ticker,
                        "isin": pos.isin,
                        "company": pos.issuer_name,
                        "short_pct": pos.position_pct,
                        "notional_gbp": pos.notional_value_gbp,
                        "report_date": pos.report_date,
                        "source": pos.source,
                    }
                    break

    return results
