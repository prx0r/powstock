"""DMO Gilts / Bank of England collector.

Fetches UK government bond yields (risk-free rate) and BoE base rate.
Free, no API key required.

Sources:
- DMO: https://www.dmo.gov.uk/resdata/opendata/gilt-repo/yield-curve
- BoE: https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp
"""

import csv
import io
import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

DMO_YIELD_URL = "https://www.dmo.gov.uk/resdata/opendata/gilt-repo/yld_CURVE.csv"
BOE_RATE_URL = "https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp"


@dataclass
class GiltYield:
    date: str
    maturity: str  # "1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "30Y", etc.
    yield_pct: float
    source: str = "dmo"


@dataclass
class BoERate:
    date: str
    rate_pct: float
    source: str = "boe"


def fetch_dmo_yields(client: httpx.Client | None = None) -> list[GiltYield]:
    """Fetch current DMO gilt yield curve.

    Note: DMO website may be behind Cloudflare captcha.
    Falls back to Bank of England base rate only if yield curve unavailable.
    """
    should_close = client is None
    if client is None:
        client = httpx.Client(timeout=30, follow_redirects=True)

    yields = []
    try:
        resp = client.get(
            DMO_YIELD_URL,
            params={"csv": "1"},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()

        # Check if we got CSV or HTML (captcha)
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type or "captcha" in resp.text[:200].lower():
            log.info("DMO behind captcha, skipping yield curve")
            return []

        reader = csv.DictReader(io.StringIO(resp.text))
        for row in reader:
            date = row.get("Date", row.get("date", ""))
            for key, val in row.items():
                if key in ("Date", "date"):
                    continue
                try:
                    yield_val = float(val)
                    yields.append(GiltYield(
                        date=date,
                        maturity=key.strip(),
                        yield_pct=yield_val,
                    ))
                except (ValueError, TypeError):
                    continue
    except Exception as e:
        log.warning("DMO yield fetch error: %s", e)
    finally:
        if should_close:
            client.close()

    return yields


def fetch_boe_rate(client: httpx.Client | None = None) -> BoERate | None:
    """Fetch latest Bank of England base rate."""
    should_close = client is None
    if client is None:
        client = httpx.Client(timeout=30, follow_redirects=True)

    try:
        resp = client.get(
            BOE_RATE_URL,
            params={
                "UsingSeries": "0",
                "FirstFromRow": "0",
                "FirstSeriesRow": "0",
                "LastFromRow": "0",
                "LastSeriesRow": "0",
                "SeriesCodes": "IUDSOIA",
                "UsingCodes": "false",
                "CSVF": "TN",
                "WhichIndex": "",
                "SeriesCodesText": "IUDSOIA",
                "UsingCodesText": "false",
                "CTY": "0",
                "fromDate": "",
                "toDate": "",
            },
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        if rows:
            last = rows[-1]
            date = last.get("DATE", last.get("date", ""))
            rate = last.get("IUDSOIA", last.get("Value", ""))
            try:
                return BoERate(date=date, rate_pct=float(rate))
            except (ValueError, TypeError):
                pass
    except Exception as e:
        log.warning("BoE rate fetch error: %s", e)
    finally:
        if should_close:
            client.close()

    return None
