"""pow_company_state_daily — the central daily state table.

Every day generates a state that cannot later be recreated perfectly.
That's the data garden.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class PowCompanyStateDaily:
    """Daily state for a company in the POW universe."""

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
    top_holders: int = 0
    psc_state: str = ""  # JSON of current PSCs
    institutional_concentration: float = 0.0
    ownership_delta_7d: float = 0.0
    ownership_delta_30d: float = 0.0

    # Insiders
    insider_buy_value_7d: float = 0.0
    insider_buy_value_90d: float = 0.0
    insider_sell_value_7d: float = 0.0
    conviction_buy_count: int = 0
    net_conviction_value: float = 0.0

    # Corporate activity
    director_join_count: int = 0
    director_leave_count: int = 0
    share_issuance: float = 0.0
    new_charges: int = 0
    charge_value: float = 0.0
    acquisitions: int = 0
    disposals: int = 0

    # Fundamentals
    turnover: float = 0.0
    inventory: float = 0.0
    cash: float = 0.0
    debt: float = 0.0
    employees: int = 0
    fixed_assets: float = 0.0
    capex_proxy: float = 0.0

    # POW external state
    constraint_score: float = 0.0
    demand_score: float = 0.0
    supply_response_score: float = 0.0
    labour_scarcity_score: float = 0.0
    planning_activity: int = 0
    procurement_activity: int = 0

    # Market state
    price: float = 0.0
    market_cap: float = 0.0
    volume: int = 0
    spread: float = 0.0
    volatility: float = 0.0

    # Derived signals
    capital_response_score: float = 0.0
    insider_alignment_score: float = 0.0
    ownership_pressure_score: float = 0.0
    constraint_exposure_score: float = 0.0
    supply_response_lag: int = 0  # days

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for storage."""
        return {
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
            "top_holders": self.top_holders,
            "psc_state": self.psc_state,
            "institutional_concentration": self.institutional_concentration,
            "ownership_delta_7d": self.ownership_delta_7d,
            "ownership_delta_30d": self.ownership_delta_30d,
            "insider_buy_value_7d": self.insider_buy_value_7d,
            "insider_buy_value_90d": self.insider_buy_value_90d,
            "insider_sell_value_7d": self.insider_sell_value_7d,
            "conviction_buy_count": self.conviction_buy_count,
            "net_conviction_value": self.net_conviction_value,
            "director_join_count": self.director_join_count,
            "director_leave_count": self.director_leave_count,
            "share_issuance": self.share_issuance,
            "new_charges": self.new_charges,
            "charge_value": self.charge_value,
            "turnover": self.turnover,
            "inventory": self.inventory,
            "cash": self.cash,
            "debt": self.debt,
            "employees": self.employees,
            "fixed_assets": self.fixed_assets,
            "capex_proxy": self.capex_proxy,
            "constraint_score": self.constraint_score,
            "demand_score": self.demand_score,
            "supply_response_score": self.supply_response_score,
            "labour_scarcity_score": self.labour_scarcity_score,
            "planning_activity": self.planning_activity,
            "procurement_activity": self.procurement_activity,
            "price": self.price,
            "market_cap": self.market_cap,
            "volume": self.volume,
            "spread": self.spread,
            "volatility": self.volatility,
            "capital_response_score": self.capital_response_score,
            "insider_alignment_score": self.insider_alignment_score,
            "ownership_pressure_score": self.ownership_pressure_score,
            "constraint_exposure_score": self.constraint_exposure_score,
            "supply_response_lag": self.supply_response_lag,
        }


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
    """Build a daily state record from available data sources."""
    from powstock.universe import BY_TICKER

    security = BY_TICKER.get(ticker)
    if not security:
        raise ValueError(f"Unknown ticker: {ticker}")

    # Extract insider metrics
    insider_buy_7d = 0.0
    insider_buy_90d = 0.0
    insider_sell_7d = 0.0
    conviction_count = 0
    net_conviction = 0.0

    if insider_data:
        insider_buy_7d = insider_data.get("buy_value_7d", 0)
        insider_buy_90d = insider_data.get("buy_value_90d", 0)
        insider_sell_7d = insider_data.get("sell_value_7d", 0)
        conviction_count = insider_data.get("conviction_buy_count", 0)
        net_conviction = insider_data.get("net_conviction_value", 0)

    # Extract ownership metrics
    psc_state = ""
    ownership_delta_7d = 0.0
    ownership_delta_30d = 0.0

    if ownership_data:
        psc_state = str(ownership_data.get("psc_state", ""))
        ownership_delta_7d = ownership_data.get("delta_7d", 0)
        ownership_delta_30d = ownership_data.get("delta_30d", 0)

    # Extract financial metrics
    turnover = 0.0
    cash = 0.0
    debt = 0.0
    employees = 0
    fixed_assets = 0.0

    if financial_data:
        turnover = financial_data.get("turnover", 0) or 0
        cash = financial_data.get("cash", 0) or 0
        debt = (financial_data.get("creditors_due_within_one_year", 0) or 0) + \
               (financial_data.get("creditors_due_after_one_year", 0) or 0)
        employees = int(financial_data.get("average_number_employees_during_period", 0) or 0)
        fixed_assets = financial_data.get("tangible_fixed_assets", 0) or 0

    # Extract filing event metrics
    director_joins = 0
    director_leaves = 0
    share_issuance = 0.0
    new_charges = 0
    charge_value = 0.0

    if filing_events:
        for event in filing_events:
            et = event.get("event_type", "")
            if et == "director_appointed":
                director_joins += 1
            elif et == "director_departed":
                director_leaves += 1
            elif et == "share_issuance":
                share_issuance += 1
            elif et == "new_charge":
                new_charges += 1

    # Extract market data
    price = 0.0
    market_cap = 0.0
    volume = 0

    if market_data:
        price = market_data.get("price", 0)
        market_cap = market_data.get("market_cap", 0)
        volume = market_data.get("volume", 0)

    # Extract POW data
    constraint_score = 0.0
    demand_score = 0.0

    if pow_data:
        constraint_score = pow_data.get("constraint_score", 0)
        demand_score = pow_data.get("demand_score", 0)

    # Compute derived signals
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
    insider_buy: float,
    share_issuance: float,
    new_charges: int,
    fixed_assets: float,
) -> float:
    """Compute capital response score (0-1)."""
    score = 0.0

    if insider_buy > 0:
        score += min(insider_buy / 1000000, 0.3)  # £1M+ insider buying = max 0.3

    if share_issuance > 0:
        score += min(share_issuance / 5, 0.3)  # 5+ issuances = max 0.3

    if new_charges > 0:
        score += min(new_charges / 3, 0.2)  # 3+ charges = max 0.2

    if fixed_assets > 0:
        score += 0.2  # Has tangible assets

    return min(score, 1.0)


def _compute_insider_alignment(
    buy_7d: float,
    sell_7d: float,
    conviction_count: int,
) -> float:
    """Compute insider alignment score (0-1)."""
    if buy_7d + sell_7d == 0:
        return 0.0

    # Net buying ratio
    net_ratio = (buy_7d - sell_7d) / (buy_7d + sell_7d)

    # Conviction bonus
    conviction_bonus = min(conviction_count * 0.1, 0.3)

    return min(max(net_ratio + conviction_bonus, 0), 1.0)
