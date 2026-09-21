"""Collector registry — maps manifest IDs to collector functions.

Every enabled manifest must have a registered collector.
run_all() derives from this registry, not hardcoded calls.

No orphan manifests. No manual runner maintenance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger(__name__)


@dataclass
class CollectorEntry:
    """A registered collector with its metadata."""
    source_id: str
    name: str
    enabled: bool
    requires_api_key: bool = False
    api_key_env: str = ""
    module: str = ""
    function: str = ""


# Registry of all collectors
COLLECTORS: dict[str, CollectorEntry] = {}


def register(
    source_id: str,
    name: str,
    enabled: bool = True,
    requires_api_key: bool = False,
    api_key_env: str = "",
    module: str = "",
    function: str = "",
) -> None:
    """Register a collector in the global registry."""
    COLLECTORS[source_id] = CollectorEntry(
        source_id=source_id,
        name=name,
        enabled=enabled,
        requires_api_key=requires_api_key,
        api_key_env=api_key_env,
        module=module,
        function=function,
    )


def get_enabled() -> list[CollectorEntry]:
    """Get all enabled collectors."""
    return [c for c in COLLECTORS.values() if c.enabled]


def get_disabled() -> list[CollectorEntry]:
    """Get all disabled collectors."""
    return [c for c in COLLECTORS.values() if not c.enabled]


def get_all() -> dict[str, CollectorEntry]:
    """Get all registered collectors."""
    return dict(COLLECTORS)


# ── Register known collectors ──────────────────────────────────────

register(
    source_id="yahoo_prices",
    name="Yahoo Finance Prices",
    enabled=True,
    module="powstock.collectors.yahoo_prices",
    function="fetch_all_latest",
)

register(
    source_id="stooq_prices",
    name="Stooq Prices",
    enabled=False,  # disabled, Yahoo is primary
    module="powstock.collectors.stooq_prices",
    function="fetch_all_latest",
)

register(
    source_id="fca_pdmr",
    name="FCA PDMR Insider Dealing",
    enabled=True,
    module="powstock.collectors.fca_pdmr",
    function="fetch_pdmr_announcements",
)

register(
    source_id="fca_short_interest",
    name="FCA Short Interest",
    enabled=True,
    module="powstock.collectors.fca_short_interest",
    function="fetch_current_short_positions",
)

register(
    source_id="rns_announcements",
    name="RNS Announcements",
    enabled=True,
    module="powstock.collectors.rns_announcements",
    function="fetch_rns_announcements",
)

register(
    source_id="companies_house",
    name="Companies House Profiles",
    enabled=True,
    requires_api_key=True,
    api_key_env="POWSTOCK_COMPANIES_HOUSE_API_KEY",
    module="powstock.collectors.companies_house",
    function="fetch_universe_companies",
)

register(
    source_id="psc_snapshot",
    name="PSC Daily Snapshot",
    enabled=True,
    module="powstock.collectors.psc_snapshot",
    function="download_psc_snapshot",
)

register(
    source_id="takeover_panel",
    name="Takeover Panel Disclosures",
    enabled=True,
    module="powstock.collectors.takeover_panel",
    function="fetch_disclosure_table",
)

register(
    source_id="tr1_notifications",
    name="FCA TR-1 Notifications",
    enabled=True,
    module="powstock.collectors.tr1_notifications",
    function="fetch_tr1_announcements",
)

register(
    source_id="filing_events",
    name="Filing Events",
    enabled=True,
    requires_api_key=True,
    api_key_env="POWSTOCK_COMPANIES_HOUSE_API_KEY",
    module="powstock.collectors.filing_events",
    function="fetch_universe_events",
)

register(
    source_id="finnhub_insider",
    name="Finnhub Insider Transactions",
    enabled=True,
    requires_api_key=True,
    api_key_env="FINNHUB_API_KEY",
    module="powstock.collectors.finnhub",
    function="fetch_universe_insiders",
)

register(
    source_id="tracefour",
    name="Tracefour PDMR",
    enabled=True,
    requires_api_key=True,
    api_key_env="TRACEFOUR_API_KEY",
    module="powstock.collectors.tracefour",
    function="fetch_uk_filings",
)

register(
    source_id="ch_company_snapshot_monthly",
    name="CH Company Snapshot (Monthly)",
    enabled=True,
    module="powstock.collectors.ch_company_snapshot",
    function="download_company_snapshot",
)

register(
    source_id="ch_accounts_bulk",
    name="CH XBRL Accounts Bulk",
    enabled=True,
    module="powstock.collectors.ch_accounts_bulk",
    function="download_accounts_bulk",
)

register(
    source_id="fca_nsm",
    name="FCA National Storage Mechanism",
    enabled=True,
    module="powstock.collectors.fca_nsm",
    function="fetch_nsm_page",
)


def print_registry() -> None:
    """Print the collector registry status."""
    enabled = get_enabled()
    disabled = get_disabled()

    print(f"\nCollector Registry:")
    print(f"  Enabled:  {len(enabled)}")
    print(f"  Disabled: {len(disabled)}")

    print(f"\n  {'ID':<25} {'Status':<10} {'API Key':<10} {'Module'}")
    print(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*30}")
    for c in COLLECTORS.values():
        status = "ON" if c.enabled else "OFF"
        api = "YES" if c.requires_api_key else "no"
        print(f"  {c.source_id:<25} {status:<10} {api:<10} {c.module}")
    print()
