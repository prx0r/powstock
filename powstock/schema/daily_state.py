"""pow_company_state_daily — the central daily state table.

Every day generates a state that cannot later be recreated perfectly.
That's the data garden.

NULL means "we don't know." Zero means "we measured zero."
These are fundamentally different things.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class PowCompanyStateDaily:
    """Daily state for a company in the POW universe.

    Nullable fields preserve absence as first-class state.
    A data garden must distinguish "we have no insider feed today"
    from "there were zero insider purchases."
    """

    # Identity
    date: date
    entity_id: str
    company_number: str
    ticker: str
    isin: str
    lei: str

    # POW classification
    pow_domains: list[str] = field(default_factory=list)
    bottlenecks: list[str] = field(default_factory=list)
    geographies: list[str] = field(default_factory=list)
    supply_chain_position: list[str] = field(default_factory=list)

    # Ownership
    top_holders: int | None = None
    psc_state: str | None = None  # JSON of current PSCs
    institutional_concentration: float | None = None
    ownership_delta_7d: float | None = None
    ownership_delta_30d: float | None = None

    # Insiders
    insider_buy_value_7d: float | None = None
    insider_buy_value_90d: float | None = None
    insider_sell_value_7d: float | None = None
    conviction_buy_count: int | None = None
    net_conviction_value: float | None = None

    # Corporate activity
    director_join_count: int | None = None
    director_leave_count: int | None = None
    share_issuance: float | None = None
    new_charges: int | None = None
    charge_value: float | None = None
    acquisitions: int | None = None
    disposals: int | None = None

    # Fundamentals
    turnover: float | None = None
    inventory: float | None = None
    cash: float | None = None
    debt: float | None = None
    employees: int | None = None
    fixed_assets: float | None = None
    capex_proxy: float | None = None

    # POW external state
    constraint_score: float | None = None
    demand_score: float | None = None
    supply_response_score: float | None = None
    labour_scarcity_score: float | None = None
    planning_activity: int | None = None
    procurement_activity: int | None = None

    # Market state
    price: float | None = None
    market_cap: float | None = None
    volume: int | None = None
    spread: float | None = None
    volatility: float | None = None

    # Derived signals
    capital_response_score: float | None = None
    insider_alignment_score: float | None = None
    ownership_pressure_score: float | None = None
    constraint_exposure_score: float | None = None
    supply_response_lag: int | None = None  # days

    # Provenance
    observed_at: str | None = None  # when POWStock collected this
    source_freshness: str | None = None  # e.g. "same_day", "1d_stale", "7d_stale"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for storage. None fields are omitted."""
        result = {
            "date": self.date.isoformat(),
            "entity_id": self.entity_id,
            "company_number": self.company_number,
            "ticker": self.ticker,
            "isin": self.isin,
            "lei": self.lei,
            "pow_domains": self.pow_domains,
            "bottlenecks": self.bottlenecks,
            "geographies": self.geographies,
            "supply_chain_position": self.supply_chain_position,
        }
        # Add nullable fields only if not None
        for field_name in [
            "top_holders", "psc_state", "institutional_concentration",
            "ownership_delta_7d", "ownership_delta_30d",
            "insider_buy_value_7d", "insider_buy_value_90d", "insider_sell_value_7d",
            "conviction_buy_count", "net_conviction_value",
            "director_join_count", "director_leave_count", "share_issuance",
            "new_charges", "charge_value", "acquisitions", "disposals",
            "turnover", "inventory", "cash", "debt", "employees",
            "fixed_assets", "capex_proxy",
            "constraint_score", "demand_score", "supply_response_score",
            "labour_scarcity_score", "planning_activity", "procurement_activity",
            "price", "market_cap", "volume", "spread", "volatility",
            "capital_response_score", "insider_alignment_score",
            "ownership_pressure_score", "constraint_exposure_score",
            "supply_response_lag",
            "observed_at", "source_freshness",
        ]:
            val = getattr(self, field_name)
            if val is not None:
                result[field_name] = val
        return result


def build_daily_state(
    ticker: str,
    state_date: date,
    insider_data: dict[str, Any] | None = None,
    ownership_data: dict[str, Any] | None = None,
    financial_data: dict[str, Any] | None = None,
    filing_events: list[dict[str, Any]] | None = None,
    market_data: dict[str, Any] | None = None,
    pow_data: dict[str, Any] | None = None,
) -> PowCompanyStateDaily:
    """Build a daily state record from available data sources.

    Missing data stays None. We never fabricate values.
    """
    from powstock.universe import BY_TICKER

    security = BY_TICKER.get(ticker)
    if not security:
        raise ValueError(f"Unknown ticker: {ticker}")

    # Insider metrics — None if no data provided
    insider_buy_7d = None
    insider_buy_90d = None
    insider_sell_7d = None
    conviction_count = None
    net_conviction = None

    if insider_data:
        insider_buy_7d = insider_data.get("buy_value_7d")
        insider_buy_90d = insider_data.get("buy_value_90d")
        insider_sell_7d = insider_data.get("sell_value_7d")
        conviction_count = insider_data.get("conviction_buy_count")
        net_conviction = insider_data.get("net_conviction_value")

    # Ownership metrics
    psc_state = None
    ownership_delta_7d = None
    ownership_delta_30d = None

    if ownership_data:
        psc_state = ownership_data.get("psc_state")
        ownership_delta_7d = ownership_data.get("delta_7d")
        ownership_delta_30d = ownership_data.get("delta_30d")

    # Financial metrics — None if not provided
    turnover = None
    cash = None
    debt = None
    employees = None
    fixed_assets = None

    if financial_data:
        turnover = financial_data.get("turnover")
        cash = financial_data.get("cash")
        creditors_within = financial_data.get("creditors_due_within_one_year") or 0
        creditors_after = financial_data.get("creditors_due_after_one_year") or 0
        debt = creditors_within + creditors_after if (creditors_within or creditors_after) else None
        employees = financial_data.get("average_number_employees_during_period")
        if employees is not None:
            employees = int(employees)
        fixed_assets = financial_data.get("tangible_fixed_assets")

    # Filing event metrics — None if no events
    director_joins = None
    director_leaves = None
    share_issuance = None
    new_charges = None
    charge_value = None

    if filing_events:
        dj = 0
        dl = 0
        si = 0
        nc = 0
        cv = 0.0
        for event in filing_events:
            et = event.get("event_type", "")
            if et == "director_appointed":
                dj += 1
            elif et == "director_departed":
                dl += 1
            elif et == "share_issuance":
                si += 1
            elif et == "new_charge":
                nc += 1
        director_joins = dj
        director_leaves = dl
        share_issuance = float(si)
        new_charges = nc

    # Market data — None if not provided
    price = None
    market_cap = None
    volume = None

    if market_data:
        price = market_data.get("price")
        market_cap = market_data.get("market_cap")
        volume = market_data.get("volume")

    # POW data — None if not provided
    constraint_score = None
    demand_score = None

    if pow_data:
        constraint_score = pow_data.get("constraint_score")
        demand_score = pow_data.get("demand_score")

    # Compute derived signals (only if inputs available)
    capital_response_score = _compute_capital_response(
        insider_buy_90d, share_issuance, new_charges, fixed_assets
    )
    insider_alignment_score = _compute_insider_alignment(
        insider_buy_7d, insider_sell_7d, conviction_count
    )

    return PowCompanyStateDaily(
        date=state_date,
        entity_id=ticker,
        company_number="",
        ticker=ticker,
        isin="",
        lei="",
        pow_domains=security.pow_layers,
        bottlenecks=security.constraints,
        insider_buy_value_7d=insider_buy_7d,
        insider_buy_value_90d=insider_buy_90d,
        insider_sell_value_7d=insider_sell_7d,
        conviction_buy_count=conviction_count,
        net_conviction_value=net_conviction,
        director_join_count=director_joins,
        director_leave_count=director_leaves,
        share_issuance=share_issuance,
        new_charges=new_charges,
        charge_value=charge_value,
        turnover=turnover,
        cash=cash,
        debt=debt,
        employees=employees,
        fixed_assets=fixed_assets,
        constraint_score=constraint_score,
        demand_score=demand_score,
        price=price,
        market_cap=market_cap,
        volume=volume,
        capital_response_score=capital_response_score,
        insider_alignment_score=insider_alignment_score,
        ownership_delta_7d=ownership_delta_7d,
        ownership_delta_30d=ownership_delta_30d,
        psc_state=psc_state,
    )


def _compute_capital_response(
    insider_buy: float | None,
    share_issuance: float | None,
    new_charges: int | None,
    fixed_assets: float | None,
) -> float | None:
    """Compute capital response score (0-1).

    Returns None if insufficient data to compute.
    """
    has_data = any(v is not None for v in [insider_buy, share_issuance, new_charges, fixed_assets])
    if not has_data:
        return None

    score = 0.0

    if insider_buy and insider_buy > 0:
        score += min(insider_buy / 1000000, 0.3)

    if share_issuance and share_issuance > 0:
        score += min(share_issuance / 5, 0.3)

    if new_charges and new_charges > 0:
        score += min(new_charges / 3, 0.2)

    if fixed_assets and fixed_assets > 0:
        score += 0.2

    return min(score, 1.0)


def _compute_insider_alignment(
    buy_7d: float | None,
    sell_7d: float | None,
    conviction_count: int | None,
) -> float | None:
    """Compute insider alignment score (0-1).

    Returns None if insufficient data to compute.
    """
    has_data = any(v is not None for v in [buy_7d, sell_7d, conviction_count])
    if not has_data:
        return None

    buy = buy_7d or 0.0
    sell = sell_7d or 0.0

    if buy + sell == 0:
        return 0.0

    # Net buying ratio
    net_ratio = (buy - sell) / (buy + sell)

    # Conviction bonus
    conv = conviction_count or 0
    conviction_bonus = min(conv * 0.1, 0.3)

    return min(max(net_ratio + conviction_bonus, 0), 1.0)
