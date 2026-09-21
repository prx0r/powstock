"""POWKernel bridge — exports powstock data as k3 nodes, edges, observations.

This is the interchange layer between powstock's domain-specific data
and powkernel's generic constraint format.

No domain concepts leak into k3. powstock is the translator.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from pow.model import Node, Edge, Observation, Evidence
from pow.canonical import canonical_id


def export_nodes(conn: sqlite3.Connection) -> list[Node]:
    """Export universe securities as k3 NODEs."""
    from powstock.universe import UNIVERSE

    nodes = []
    for security in UNIVERSE:
        node = Node(
            id=f"powstock:{security.ticker}",
            kind="security",
            label=security.company,
            metadata={
                "ticker": security.ticker,
                "exchange": security.exchange,
                "isin": security.isin,
                "company_number": security.company_number,
                "pow_layers": security.pow_layers,
                "constraints": security.constraints,
                "dataset": security.dataset,
            },
        )
        nodes.append(node)

    # Add constraint nodes from POW layers
    all_layers: set[str] = set()
    for s in UNIVERSE:
        all_layers.update(s.pow_layers)

    for layer in sorted(all_layers):
        nodes.append(Node(
            id=f"powstock:constraint:{layer}",
            kind="constraint",
            label=layer.replace("_", " ").title(),
            metadata={"source": "powstock_universe"},
        ))

    return nodes


def export_edges(conn: sqlite3.Connection) -> list[Edge]:
    """Export supply chain relationships as k3 EDGEs (REQUIRES only).

    Maps pow_layers to constraint edges:
    if a security has constraint X, it REQUIRES X to be satisfied.
    """
    from powstock.universe import UNIVERSE

    edges = []
    seen = set()

    for security in UNIVERSE:
        for constraint in security.constraints:
            edge = Edge(
                source=f"powstock:{security.ticker}",
                target=f"powstock:constraint:{constraint}",
                relation="REQUIRES",
            )
            edge_id = canonical_id(edge)
            if edge_id not in seen:
                edges.append(edge)
                seen.add(edge_id)

    return edges


def export_observations(conn: sqlite3.Connection) -> list[Observation]:
    """Export price, insider, and short interest data as k3 OBSERVATIONs."""
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
        observations.append(Observation(
            metric="price_gbp",
            subject=f"powstock:{ticker}",
            value=close,
            unit="GBP",
            as_of=date,
            source="yahoo_finance",
        ))
        observations.append(Observation(
            metric="daily_volume",
            subject=f"powstock:{ticker}",
            value=volume,
            unit="shares",
            as_of=date,
            source="yahoo_finance",
        ))

    # Short interest observations
    rows = conn.execute("""
        SELECT ticker, position_pct, effective_at
        FROM short_interest
        WHERE ticker IS NOT NULL
    """).fetchall()

    for ticker, pct, date in rows:
        observations.append(Observation(
            metric="short_interest_pct",
            subject=f"powstock:{ticker}",
            value=pct,
            unit="percent",
            as_of=date or "",
            source="fca_ansp",
        ))

    # Insider deal observations
    rows = conn.execute("""
        SELECT ticker, action, SUM(value) as total, COUNT(*) as cnt
        FROM insider_deals
        WHERE ticker IS NOT NULL
        GROUP BY ticker, action
    """).fetchall()

    for ticker, action, total, cnt in rows:
        metric = "insider_buy_value" if action == "Purchase" else "insider_sell_value"
        observations.append(Observation(
            metric=metric,
            subject=f"powstock:{ticker}",
            value=total,
            unit="GBP",
            as_of="",
            source="investegate_pdmr",
        ))

    # Company profile observations
    rows = conn.execute("""
        SELECT ticker, officers_count, charges_count, psc_count
        FROM company_profiles
    """).fetchall()

    for ticker, officers, charges, psc in rows:
        observations.append(Observation(
            metric="officers_count",
            subject=f"powstock:{ticker}",
            value=officers,
            unit="person",
            as_of="",
            source="companies_house",
        ))

    return observations


def export_evidence(conn: sqlite3.Connection) -> list[Evidence]:
    """Export data sources as k3 EVIDENCE objects."""
    evidence = []

    # Price evidence
    evidence.append(Evidence(
        claim="Yahoo Finance provides daily OHLCV for LSE-listed securities",
        target="obs:price",
        direction="SUPPORTS",
        source_uri="https://query1.finance.yahoo.com",
        publisher="Yahoo Finance",
        published_at="",
        observed_at="",
        lineage_root="yahoo_finance",
    ))

    # Short interest evidence
    evidence.append(Evidence(
        claim="FCA publishes aggregated net short positions daily",
        target="obs:short_interest",
        direction="SUPPORTS",
        source_uri="https://www.fca.org.uk/publication/documents/aggregated-net-short-positions.xlsx",
        publisher="FCA",
        published_at="",
        observed_at="",
        lineage_root="fca_ansp",
    ))

    # Insider dealing evidence
    evidence.append(Evidence(
        claim="FCA PDMR notifications published via Investegate",
        target="obs:insider_deals",
        direction="SUPPORTS",
        source_uri="https://www.investegate.co.uk",
        publisher="Investegate/FCA",
        published_at="",
        observed_at="",
        lineage_root="investegate_pdmr",
    ))

    # Company data evidence
    evidence.append(Evidence(
        claim="Companies House provides company profiles and officer data",
        target="obs:company_profiles",
        direction="SUPPORTS",
        source_uri="https://api.company-information.service.gov.uk",
        publisher="Companies House",
        published_at="",
        observed_at="",
        lineage_root="companies_house",
    ))

    return evidence


def export_all(conn: sqlite3.Connection) -> dict[str, list]:
    """Export all powstock data as k3 objects.

    Returns: {"nodes": [...], "edges": [...], "observations": [...], "evidence": [...]}
    """
    return {
        "nodes": export_nodes(conn),
        "edges": export_edges(conn),
        "observations": export_observations(conn),
        "evidence": export_evidence(conn),
    }


def print_export_summary(export: dict[str, list]) -> None:
    """Print summary of exported k3 objects."""
    print(f"\nPOWKernel Export Summary:")
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
