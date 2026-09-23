"""powstock collectors — UK stock data acquisition.

All 20 collector modules. Some require API keys, some are blocked by external services.
See BLOCKERS.md for status of each.
"""

# Core collectors (no API key required)
from powstock.collectors.yahoo_prices import fetch_all_latest, fetch_latest, get_moves
from powstock.collectors.stooq_prices import fetch_latest as stooq_fetch_latest
from powstock.collectors.fca_pdmr import fetch_pdmr_announcements, fetch_ticker_insiders
from powstock.collectors.fca_short_interest import fetch_current_short_positions, fetch_all_short_interest
from powstock.collectors.rns_announcements import fetch_rns_announcements, fetch_ticker_rns
from powstock.collectors.companies_house import fetch_company_profile, fetch_universe_companies
from powstock.collectors.psc_snapshot import fetch_universe_psc, download_psc_snapshot
from powstock.collectors.filing_events import fetch_universe_events, classify_filing
from powstock.collectors.takeover_panel import fetch_disclosure_table, parse_disclosure_forms
from powstock.collectors.tr1_notifications import fetch_tr1_announcements
from powstock.collectors.uk_parliament import fetch_all_mp_shareholdings
from powstock.collectors.congress_trades import fetch_congress_trades
from powstock.collectors.european_insiders import fetch_european_insiders
from powstock.collectors.dmo_gilts import fetch_dmo_yields, fetch_boe_rate
from powstock.collectors.commodity_prices import fetch_all_commodity_prices
from powstock.collectors.ch_company_snapshot import download_company_snapshot
from powstock.collectors.ch_accounts_bulk import download_accounts_bulk
from powstock.collectors.fca_nsm import fetch_nsm_page

# API key required collectors
from powstock.collectors.finnhub import fetch_universe_insiders
from powstock.collectors.tracefour import fetch_uk_filings

# Orchestrator
from powstock.collectors.runner import init_db, run_all, status

__all__ = [
    # Prices
    "fetch_all_latest",
    "fetch_latest",
    "get_moves",
    "stooq_fetch_latest",
    # Insider dealing
    "fetch_pdmr_announcements",
    "fetch_ticker_insiders",
    "fetch_universe_insiders",
    "fetch_uk_filings",
    # Short interest
    "fetch_current_short_positions",
    "fetch_all_short_interest",
    # RNS
    "fetch_rns_announcements",
    "fetch_ticker_rns",
    # Companies House
    "fetch_company_profile",
    "fetch_universe_companies",
    "download_psc_snapshot",
    "fetch_universe_psc",
    "fetch_universe_events",
    "classify_filing",
    "download_company_snapshot",
    "download_accounts_bulk",
    # Regulatory
    "fetch_disclosure_table",
    "parse_disclosure_forms",
    "fetch_tr1_announcements",
    "fetch_nsm_page",
    # Geographic collectors
    "fetch_all_mp_shareholdings",
    "fetch_congress_trades",
    "fetch_european_insiders",
    # Macro
    "fetch_dmo_yields",
    "fetch_boe_rate",
    "fetch_all_commodity_prices",
    # Orchestrator
    "init_db",
    "run_all",
    "status",
]
