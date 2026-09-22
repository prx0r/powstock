"""European Insider Trading collector.

Fetches insider dealings from BaFin (Germany), AMF (France), AFM (Netherlands).
All free, no API key required.

Reference: reference/insider-scanner/bafin.py, amf.py, afm.py
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger(__name__)

BAFIN_URL = "https://portal.mvp.bafin.de/database/DealingsInfo/sucheForm.do"
BAFIN_START_URL = "https://portal.mvp.bafin.de/database/DealingsInfo/start.do"
AMF_URL = "https://bdif.amf-france.org/back/api/v1/informations"
AFM_URL = "https://www.afm.nl/api/DealersDealings/DealerDealings/SearchDealing"

REQUEST_DELAY = 2.0  # seconds between requests


@dataclass
class EuropeanInsiderTrade:
    source: str  # "bafin", "amf", "afm"
    isin: str
    issuer_name: str
    insider_name: str
    position: str
    tx_type: str  # "Buy", "Sell", "Other"
    tx_date: str
    price: float | None = None
    volume: int | None = None
    currency: str = ""
    filing_date: str = ""
    raw: dict = field(default_factory=dict)


# ── BaFin (Germany) ──────────────────────────────────────────────

BAFIN_TRADE_MAP = {"kauf": "Buy", "verkauf": "Sell", "sonstiges": "Other"}
BAFIN_INSTRUMENT_MAP = {
    "aktie": "Share", "schuldtitel": "Debt Instrument",
    "derivat": "Derivative", "option": "Option",
}


def fetch_bafin_trades(
    isin: str,
    client: httpx.Client,
) -> list[EuropeanInsiderTrade]:
    """Fetch German insider trades for an ISIN from BaFin."""
    trades = []

    try:
        # Init session
        client.get(BAFIN_START_URL, timeout=15)
        time.sleep(0.5)

        # Search by ISIN
        resp = client.post(
            BAFIN_URL,
            data={
                "emittentIsin": isin,
                "emittentName": "",
                "emittentButton": "Suche Emittent",
                "meldepflichtigerName": "",
                "zeitraum": "0",
                "zeitraumVon": "",
                "zeitraumBis": "",
                "locale": "en_GB",
            },
            timeout=30,
        )
        resp.raise_for_status()

        # Parse HTML table
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", resp.text, re.DOTALL)
        for row in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            if len(cells) >= 8:
                clean = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
                trades.append(EuropeanInsiderTrade(
                    source="bafin",
                    isin=isin,
                    issuer_name=clean[0] if len(clean) > 0 else "",
                    insider_name=clean[3] if len(clean) > 3 else "",
                    position=clean[4] if len(clean) > 4 else "",
                    tx_type=BAFIN_TRADE_MAP.get(clean[6].lower(), "Other") if len(clean) > 6 else "Other",
                    tx_date=clean[7] if len(clean) > 7 else "",
                    raw={"cells": clean},
                ))
    except Exception as e:
        log.warning("BaFin error for %s: %s", isin, e)

    return trades


# ── AMF (France) ─────────────────────────────────────────────────


def fetch_amf_trades(
    isin: str,
    client: httpx.Client,
    max_results: int = 50,
) -> list[EuropeanInsiderTrade]:
    """Fetch French insider trades for an ISIN from AMF BDIF."""
    trades = []

    try:
        resp = client.get(
            AMF_URL,
            params={
                "rechercheTexte": isin,
                "typesInformation": "DD",
                "From": 0,
                "Size": max_results,
            },
            headers={
                "Referer": "https://bdif.amf-france.org/",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        for result in data.get("result", []):
            pub_date = result.get("datePublication", "")
            info_date = result.get("dateInformation", "")
            companies = result.get("societes", [])
            issuer = companies[0].get("raisonSociale", "") if companies else ""

            # AMF provides PDF documents — we'd need to download and parse
            # For now, store the metadata
            trades.append(EuropeanInsiderTrade(
                source="amf",
                isin=isin,
                issuer_name=issuer,
                insider_name="",
                position="",
                tx_type="",
                tx_date=info_date,
                filing_date=pub_date,
                raw=result,
            ))
    except Exception as e:
        log.warning("AMF error for %s: %s", isin, e)

    return trades


# ── AFM (Netherlands) ────────────────────────────────────────────

AFM_TRADE_MAP = {
    "koop": "Buy", "aankoop": "Buy", "buy": "Buy", "purchase": "Buy",
    "verkoop": "Sell", "sell": "Sell", "disposal": "Sell",
}


def fetch_afm_trades(
    isin: str,
    client: httpx.Client,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[EuropeanInsiderTrade]:
    """Fetch Dutch insider trades for an ISIN from AFM.

    Note: AFM API URL may have changed. Returns empty on failure.
    """
    trades = []

    try:
        params: dict[str, Any] = {
            "isin": isin,
            "pageNumber": 1,
            "pageSize": 100,
        }
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to

        resp = client.get(
            AFM_URL,
            params=params,
            headers={"Referer": "https://www.afm.nl/", "User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        resp.raise_for_status()

        # Check if we got JSON or HTML (API changed)
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type:
            log.debug("AFM returned HTML (API may have changed), skipping")
            return []

        data = resp.json()
        records = data if isinstance(data, list) else data.get("results", data.get("items", []))

        for rec in records:
            tx_type_raw = rec.get("transactionType", rec.get("typeTransactie", "")).lower()
            trades.append(EuropeanInsiderTrade(
                source="afm",
                isin=rec.get("isin", isin),
                issuer_name=rec.get("issuerName", rec.get("emittent", "")),
                insider_name=rec.get("personName", rec.get("name", rec.get("naam", ""))),
                position=rec.get("function", rec.get("functie", "")),
                tx_type=AFM_TRADE_MAP.get(tx_type_raw, "Other"),
                tx_date=rec.get("transactionDate", rec.get("datumTransactie", "")),
                price=rec.get("price", rec.get("prijs")),
                volume=rec.get("volume", rec.get("aantal")),
                currency=rec.get("currency", "EUR"),
                filing_date=rec.get("publicationDate", rec.get("datumPublicatie", "")),
                raw=rec,
            ))
    except Exception as e:
        log.debug("AFM error for %s: %s", isin, e)

    return trades


# ── Combined ──────────────────────────────────────────────────────


def fetch_european_insiders(
    isins: list[str] | None = None,
    client: httpx.Client | None = None,
) -> list[EuropeanInsiderTrade]:
    """Fetch insider trades from all European regulators for given ISINs."""
    if isins is None:
        from powstock.universe import UNIVERSE
        isins = [s.isin for s in UNIVERSE[:5] if s.isin and not s.isin.startswith("CH")]  # limit for speed

    should_close = client is None
    if client is None:
        client = httpx.Client(timeout=30, follow_redirects=True)

    all_trades = []

    try:
        for isin in isins:
            if not isin:
                continue

            # BaFin
            trades = fetch_bafin_trades(isin, client)
            all_trades.extend(trades)
            time.sleep(REQUEST_DELAY)

            # AFM
            trades = fetch_afm_trades(isin, client)
            all_trades.extend(trades)
            time.sleep(REQUEST_DELAY)

            # AMF (slower — PDF-based)
            trades = fetch_amf_trades(isin, client)
            all_trades.extend(trades)
            time.sleep(REQUEST_DELAY)
    finally:
        if should_close:
            client.close()

    return all_trades
