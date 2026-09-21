"""Universe integrity tests.

Verifies that the 25 security definitions are complete and consistent.
"""

import json
from pathlib import Path

from powstock.universe import BY_TICKER, CONSTRAINT, LIQUID, UNIVERSE


def test_universe_count():
    """Universe must contain exactly 25 securities."""
    assert len(UNIVERSE) == 25


def test_all_tickers_unique():
    """No duplicate tickers."""
    tickers = [s.ticker for s in UNIVERSE]
    assert len(tickers) == len(set(tickers))


def test_all_have_company_number():
    """Every UK-listed equity must have a hard-coded Companies House number.
    ETPs (exchange-traded products) are excluded — they're not UK companies."""
    for s in UNIVERSE:
        if s.market_cap == "ETP":
            continue
        assert s.company_number, f"{s.ticker} missing company_number"


def test_all_have_isin():
    """Every security must have an ISIN."""
    for s in UNIVERSE:
        assert s.isin, f"{s.ticker} missing isin"


def test_by_ticker_lookup():
    """BY_TICKER must contain all tickers."""
    assert len(BY_TICKER) == 25
    for s in UNIVERSE:
        assert s.ticker in BY_TICKER
        assert BY_TICKER[s.ticker] is s


def test_dataset_splits():
    """Liquid + constraint must cover all universe entries."""
    assert len(LIQUID) + len(CONSTRAINT) == len(UNIVERSE)
    for s in LIQUID:
        assert s.dataset == "liquid"
    for s in CONSTRAINT:
        assert s.dataset == "constraint"


def test_pow_layers_not_empty():
    """Every security must have at least one POW layer."""
    for s in UNIVERSE:
        assert len(s.pow_layers) > 0, f"{s.ticker} has no pow_layers"


def test_constraints_not_empty():
    """Every security must have at least one constraint."""
    for s in UNIVERSE:
        assert len(s.constraints) > 0, f"{s.ticker} has no constraints"
