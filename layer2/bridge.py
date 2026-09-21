"""POWKernel bridge — exports powstock data in canonical powk format.

Aligns with prx0r/powk (the canonical kernel):
- Node IDs are domain-supplied (not content-addressed)
- Edge contains only structural dependency + coefficient
- All time-varying data lives in Observation (bitemporal)
- Evidence does NOT contain values
- Derivation includes model_hash and unknowns

No domain concepts leak into powk. powstock is the Layer 1 adapter.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from pow.model import (
    Node, Edge, Observation, Evidence, Derivation,
    make_edge_id, make_obs_id, make_ev_id,
)
from pow.canonical import content_id


def _now() -> str:
    return datetime.now().isoformat()


def export_nodes(conn: sqlite3.Connection) -> list[Node]:
    """Export universe securities as powk NODEs.

    Node IDs are domain-supplied: "powstock:TICKER"
    """
    from powstock.universe import UNIVERSE

    nodes = []
    for security in UNIVERSE:
        nodes.append(Node(
            id=f"powstock:{security.ticker}",
            kind="security",
            label=security.company,
        ))

    # Add constraint nodes from POW layers
    all_layers: set[str] = set()
    for s in UNIVERSE:
        all_layers.update(s.pow_layers)

    for layer in sorted(all_layers):
        nodes.append(Node(
            id=f"powstock:constraint:{layer}",
            kind="constraint",
            label=layer.replace("_", " ").title(),
        ))

    return nodes


def export_edges(conn: sqlite3.Connection) -> list[Edge]:
    """Export supply chain relationships as powk EDGEs (REQUIRES only).

    Edge contains only structural dependency. Time-varying properties
    (capacity, utilisation, lead_time) become OBSERVATIONs targeting the edge.
    """
    from powstock.universe import UNIVERSE

    edges = []
    seen = set()

    for security in UNIVERSE:
        for constraint in security.constraints:
            edge_id = make_edge_id(
                f"powstock:{security.ticker}",
                f"powstock:constraint:{constraint}",
                "REQUIRES",
            )
            if edge_id not in seen:
                edges.append(Edge(
                    id=edge_id,
                    source=f"powstock:{security.ticker}",
                    target=f"powstock:constraint:{constraint}",
                    relation="REQUIRES",
                ))
                seen.add(edge_id)

    return edges


def export_observations(conn: sqlite3.Connection) -> list[Observation]:
    """Export price, insider, and short interest data as powk OBSERVATIONs.

    Bitemporal: effective_at (when true in world), observed_at (when we learned it).
    """
    now = _now()
    observations = []

    # Price observations (latest for each ticker)
    rows = conn.execute("""
        SELECT ticker, close, date, volume
        FROM price_daily
        WHERE (ticker, date) IN (
            SELECT ticker, MAX(date) FROM price_daily GROUP BY ticker
        )
    """).fetchall()

    for ticker, close, date, volume in rows:
        subject = f"powstock:{ticker}"

        observations.append(Observation(
            id=make_obs_id(subject, "price_gbp", date, "yahoo_finance"),
            subject=subject,
            metric="price_gbp",
            value=close,
            unit="GBP",
            effective_at=date,
            observed_at=now,
            source_dataset="yahoo_finance",
        ))

        observations.append(Observation(
            id=make_obs_id(subject, "daily_volume", date, "yahoo_finance"),
            subject=subject,
            metric="daily_volume",
            value=float(volume),
            unit="shares",
            effective_at=date,
            observed_at=now,
            source_dataset="yahoo_finance",
        ))

    # Short interest observations
    rows = conn.execute("""
        SELECT ticker, position_pct, effective_at
        FROM short_interest
        WHERE ticker IS NOT NULL
    """).fetchall()

    for ticker, pct, date in rows:
        subject = f"powstock:{ticker}"
        eff = date or now

        observations.append(Observation(
            id=make_obs_id(subject, "short_interest_pct", eff, "fca_ansp"),
            subject=subject,
            metric="short_interest_pct",
            value=pct,
            unit="percent",
            effective_at=eff,
            observed_at=now,
            source_dataset="fca_ansp",
        ))

    # Insider deal observations
    rows = conn.execute("""
        SELECT ticker, action, SUM(value) as total, COUNT(*) as cnt
        FROM insider_deals
        WHERE ticker IS NOT NULL
        GROUP BY ticker, action
    """).fetchall()

    for ticker, action, total, cnt in rows:
        subject = f"powstock:{ticker}"
        metric = "insider_buy_value" if action == "Purchase" else "insider_sell_value"

        observations.append(Observation(
            id=make_obs_id(subject, metric, now, "investegate_pdmr"),
            subject=subject,
            metric=metric,
            value=total,
            unit="GBP",
            effective_at=now,
            observed_at=now,
            source_dataset="investegate_pdmr",
        ))

    # Company profile observations
    rows = conn.execute("""
        SELECT ticker, officers_count, charges_count, psc_count, observed_at
        FROM company_profiles
    """).fetchall()

    for ticker, officers, charges, psc, obs_at in rows:
        subject = f"powstock:{ticker}"
        eff = obs_at or now

        observations.append(Observation(
            id=make_obs_id(subject, "officers_count", eff, "companies_house"),
            subject=subject,
            metric="officers_count",
            value=float(officers) if officers else None,
            unit="person",
            effective_at=eff,
            observed_at=now,
            source_dataset="companies_house",
        ))

    return observations


def export_evidence(conn: sqlite3.Connection) -> list[Evidence]:
    """Export data sources as powk EVIDENCE objects.

    Evidence does NOT contain numeric values — those live in Observations.
    """
    evidence = []

    # Price evidence
    evidence.append(Evidence(
        id=make_ev_id("obs:price", "SUPPORTS",
                       "Yahoo Finance provides daily OHLCV for LSE-listed securities",
                       "Yahoo Finance"),
        target="obs:price",
        direction="SUPPORTS",
        claim="Yahoo Finance provides daily OHLCV for LSE-listed securities",
        source_uri="https://query1.finance.yahoo.com",
        publisher="Yahoo Finance",
        lineage_root="yahoo_finance",
    ))

    # Short interest evidence
    evidence.append(Evidence(
        id=make_ev_id("obs:short_interest", "SUPPORTS",
                       "FCA publishes aggregated net short positions daily",
                       "FCA"),
        target="obs:short_interest",
        direction="SUPPORTS",
        claim="FCA publishes aggregated net short positions daily",
        source_uri="https://www.fca.org.uk/publication/documents/aggregated-net-short-positions.xlsx",
        publisher="FCA",
        lineage_root="fca_ansp",
    ))

    # Insider dealing evidence
    evidence.append(Evidence(
        id=make_ev_id("obs:insider_deals", "SUPPORTS",
                       "FCA PDMR notifications published via Investegate",
                       "Investegate/FCA"),
        target="obs:insider_deals",
        direction="SUPPORTS",
        claim="FCA PDMR notifications published via Investegate",
        source_uri="https://www.investegate.co.uk",
        publisher="Investegate/FCA",
        lineage_root="investegate_pdmr",
    ))

    # Company data evidence
    evidence.append(Evidence(
        id=make_ev_id("obs:company_profiles", "SUPPORTS",
                       "Companies House provides company profiles and officer data",
                       "Companies House"),
        target="obs:company_profiles",
        direction="SUPPORTS",
        claim="Companies House provides company profiles and officer data",
        source_uri="https://api.company-information.service.gov.uk",
        publisher="Companies House",
        lineage_root="companies_house",
    ))

    return evidence


def export_all(conn: sqlite3.Connection) -> dict[str, list]:
    """Export all powstock data as powk objects.

    Returns: {"nodes": [...], "edges": [...], "observations": [...], "evidence": [...]}
    """
    return {
        "nodes": export_nodes(conn),
        "edges": export_edges(conn),
        "observations": export_observations(conn),
        "evidence": export_evidence(conn),
    }


def print_export_summary(export: dict[str, list]) -> None:
    """Print summary of exported powk objects."""
    print(f"\nPOWKernel Export Summary (canonical format):")
    print(f"  Nodes:       {len(export['nodes'])}")
    print(f"  Edges:       {len(export['edges'])}")
    print(f"  Observations: {len(export['observations'])}")
    print(f"  Evidence:    {len(export['evidence'])}")

    # Node breakdown
    node_kinds: dict[str, int] = {}
    for n in export["nodes"]:
        node_kinds[n.kind] = node_kinds.get(n.kind, 0) + 1
    print(f"\n  Node types:")
    for kind, count in sorted(node_kinds.items()):
        print(f"    {kind}: {count}")

    # Observation breakdown
    obs_metrics: dict[str, int] = {}
    for o in export["observations"]:
        obs_metrics[o.metric] = obs_metrics.get(o.metric, 0) + 1
    print(f"\n  Observation types:")
    for metric, count in sorted(obs_metrics.items()):
        print(f"    {metric}: {count}")
