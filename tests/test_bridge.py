"""POWKernel bridge tests."""

import sqlite3
from pathlib import Path

import pytest

DB_PATH = Path(__file__).parent.parent / "data" / "powstock.db"


def _get_conn():
    if DB_PATH.exists():
        return sqlite3.connect(str(DB_PATH))
    return None


def test_export_nodes():
    from layer2.bridge import export_nodes
    conn = _get_conn()
    if conn is None:
        return
    nodes = export_nodes(conn)
    assert len(nodes) > 0
    # Must have security nodes
    security_nodes = [n for n in nodes if n.kind == "security"]
    assert len(security_nodes) == 25
    # Must have constraint nodes
    constraint_nodes = [n for n in nodes if n.kind == "constraint"]
    assert len(constraint_nodes) > 0
    conn.close()


def test_export_edges():
    from layer2.bridge import export_edges
    from pow.canonical import canonical_id
    conn = _get_conn()
    if conn is None:
        return
    edges = export_edges(conn)
    assert len(edges) > 0
    for e in edges:
        assert e.relation == "REQUIRES"
        cid = canonical_id(e)
        assert len(cid) == 16
    conn.close()


def test_export_observations():
    from layer2.bridge import export_observations
    conn = _get_conn()
    if conn is None:
        return
    obs = export_observations(conn)
    assert len(obs) > 0
    # Must have price observations
    prices = [o for o in obs if o.metric == "price_gbp"]
    assert len(prices) > 0
    for p in prices:
        assert p.value > 0
        assert p.unit == "GBP"
    conn.close()


def test_export_evidence():
    from layer2.bridge import export_evidence
    conn = _get_conn()
    if conn is None:
        return
    evidence = export_evidence(conn)
    assert len(evidence) >= 4
    for e in evidence:
        assert e.direction == "SUPPORTS"
        assert e.lineage_root != ""
    conn.close()


def test_export_all():
    from layer2.bridge import export_all
    conn = _get_conn()
    if conn is None:
        return
    export = export_all(conn)
    assert "nodes" in export
    assert "edges" in export
    assert "observations" in export
    assert "evidence" in export
    assert len(export["nodes"]) > 0
    assert len(export["edges"]) > 0
    assert len(export["observations"]) > 0
    conn.close()
