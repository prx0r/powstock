"""powstock API — HTTP interface for all data.

Exposes every collector, every table, every signal via REST endpoints.
powops, dashboards, and external tools can query this.

Usage:
    python -m powstock.api
    # or
    uvicorn powstock.api:app --host 0.0.0.0 --port 8797
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

DB_PATH = Path("data/powstock.db")

app = FastAPI(
    title="powstock API",
    description="UK physical-economy capital-allocation observatory",
    version="0.1.0",
)


def get_db() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    """Convert sqlite3.Row to dict."""
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows: list[sqlite3.Row]) -> list[dict]:
    """Convert list of sqlite3.Row to list of dicts."""
    return [dict(r) for r in rows]


# ── Health ──────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    """System health check."""
    conn = get_db()
    try:
        tables = {}
        for table in ["price_daily", "insider_deals", "short_interest",
                       "rns_announcements", "company_profiles", "ingest_run",
                       "artifact_object", "observation"]:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            tables[table] = count

        last_run = conn.execute(
            "SELECT source, started_at, status FROM ingest_run ORDER BY run_id DESC LIMIT 1"
        ).fetchone()

        return {
            "status": "ok",
            "database": str(DB_PATH),
            "tables": tables,
            "last_run": row_to_dict(last_run),
            "checked_at": datetime.now().isoformat(),
        }
    finally:
        conn.close()


@app.get("/heartbeat")
def heartbeat() -> dict:
    """Read heartbeat file (written by run_all)."""
    hb_path = Path("data/heartbeat.json")
    if hb_path.exists():
        return json.loads(hb_path.read_text())
    return {"error": "no heartbeat file", "heartbeat_at": None}


# ── Universe ────────────────────────────────────────────────────

@app.get("/universe")
def universe() -> list[dict]:
    """List all 25 universe securities."""
    from powstock.universe import UNIVERSE
    return [
        {
            "ticker": s.ticker,
            "company": s.company,
            "isin": s.isin,
            "lei": s.lei,
            "company_number": s.company_number,
            "dataset": s.dataset,
        }
        for s in UNIVERSE
    ]


@app.get("/universe/{ticker}")
def universe_ticker(ticker: str) -> dict:
    """Get details for a specific ticker."""
    from powstock.universe import UNIVERSE, BY_TICKER
    t = ticker.upper()
    if t not in BY_TICKER:
        return {"error": f"Ticker {t} not in universe"}
    s = BY_TICKER[t]
    return {
        "ticker": s.ticker,
        "company": s.company,
        "isin": s.isin,
        "lei": s.lei,
        "company_number": s.company_number,
        "dataset": s.dataset,
    }


# ── Prices ──────────────────────────────────────────────────────

@app.get("/prices")
def prices(
    ticker: str | None = None,
    days: int = Query(30, ge=1, le=3650),
) -> list[dict] | dict:
    """Get price history."""
    conn = get_db()
    try:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM price_daily WHERE ticker = ? ORDER BY date DESC LIMIT ?",
                (ticker.upper(), days),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM price_daily ORDER BY date DESC LIMIT ?",
                (days * 25,),  # approximate
            ).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


@app.get("/prices/latest")
def prices_latest() -> list[dict]:
    """Get latest price for each ticker."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT p.* FROM price_daily p
            INNER JOIN (SELECT ticker, MAX(date) as max_date FROM price_daily GROUP BY ticker) m
            ON p.ticker = m.ticker AND p.date = m.max_date
            ORDER BY p.ticker
        """).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


@app.get("/prices/{ticker}")
def prices_ticker(ticker: str, days: int = Query(30, ge=1, le=3650)) -> list[dict]:
    """Get price history for a specific ticker."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM price_daily WHERE ticker = ? ORDER BY date DESC LIMIT ?",
            (ticker.upper(), days),
        ).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


# ── Insider Deals ───────────────────────────────────────────────

@app.get("/insiders")
def insiders(ticker: str | None = None, limit: int = Query(100, ge=1, le=1000)) -> list[dict]:
    """Get insider dealing transactions."""
    conn = get_db()
    try:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM insider_deals WHERE ticker = ? ORDER BY effective_at DESC LIMIT ?",
                (ticker.upper(), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM insider_deals ORDER BY effective_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


# ── Short Interest ──────────────────────────────────────────────

@app.get("/short_interest")
def short_interest(ticker: str | None = None, limit: int = Query(100, ge=1, le=1000)) -> list[dict]:
    """Get FCA short interest positions."""
    conn = get_db()
    try:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM short_interest WHERE ticker = ? ORDER BY effective_at DESC LIMIT ?",
                (ticker.upper(), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM short_interest ORDER BY effective_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


# ── RNS Announcements ──────────────────────────────────────────

@app.get("/rns")
def rns(ticker: str | None = None, limit: int = Query(100, ge=1, le=1000)) -> list[dict]:
    """Get RNS announcements."""
    conn = get_db()
    try:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM rns_announcements WHERE ticker = ? ORDER BY effective_at DESC LIMIT ?",
                (ticker.upper(), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM rns_announcements ORDER BY effective_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


# ── Company Profiles ────────────────────────────────────────────

@app.get("/companies")
def companies(ticker: str | None = None) -> list[dict]:
    """Get company profiles."""
    conn = get_db()
    try:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM company_profiles WHERE ticker = ?",
                (ticker.upper(),),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM company_profiles ORDER BY ticker").fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


@app.get("/companies/{ticker}")
def companies_ticker(ticker: str) -> dict:
    """Get company profile for a specific ticker."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM company_profiles WHERE ticker = ?",
            (ticker.upper(),),
        ).fetchone()
        if row is None:
            return {"error": f"No profile for {ticker.upper()}"}
        return row_to_dict(row)
    finally:
        conn.close()


# ── Signals ─────────────────────────────────────────────────────

@app.get("/signals/{ticker}")
def signals(ticker: str) -> dict:
    """Compute all signals for a ticker."""
    conn = get_db()
    try:
        from layer2.signals import compute_all_signals
        results = compute_all_signals(conn, ticker.upper())
        return {
            "ticker": ticker.upper(),
            "signals": results,
            "computed_at": datetime.now().isoformat(),
        }
    finally:
        conn.close()


@app.get("/signals/{ticker}/{signal_name}")
def signals_single(ticker: str, signal_name: str) -> dict:
    """Compute a specific signal for a ticker."""
    conn = get_db()
    try:
        from layer2 import signals as sig_module
        func = getattr(sig_module, signal_name, None)
        if func is None:
            return {"error": f"Unknown signal: {signal_name}"}
        result = func(conn, ticker.upper())
        if result is None:
            return {"ticker": ticker.upper(), "signal": signal_name, "value": None}
        return {
            "ticker": ticker.upper(),
            "signal": signal_name,
            "value": result.value if hasattr(result, "value") else result,
            "confidence": result.confidence if hasattr(result, "confidence") else None,
            "metadata": result.metadata if hasattr(result, "metadata") else None,
        }
    finally:
        conn.close()


# ── Ingest Runs ─────────────────────────────────────────────────

@app.get("/runs")
def runs(limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    """Get recent ingest runs."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM ingest_run ORDER BY run_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


@app.get("/runs/{source}")
def runs_source(source: str, limit: int = Query(10, ge=1, le=100)) -> list[dict]:
    """Get ingest runs for a specific source."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM ingest_run WHERE source = ? ORDER BY run_id DESC LIMIT ?",
            (source, limit),
        ).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


# ── Observations ────────────────────────────────────────────────

@app.get("/observations")
def observations(
    ticker: str | None = None,
    source: str | None = None,
    metric: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
) -> list[dict]:
    """Get raw observations/metrics."""
    conn = get_db()
    try:
        query = "SELECT * FROM observation WHERE 1=1"
        params = []
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker.upper())
        if source:
            query += " AND source = ?"
            params.append(source)
        if metric:
            query += " AND metric = ?"
            params.append(metric)
        query += " ORDER BY observed_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


# ── Artifacts ───────────────────────────────────────────────────

@app.get("/artifacts")
def artifacts(source: str | None = None, limit: int = Query(50, ge=1, le=500)) -> list[dict]:
    """Get stored artifacts (content-addressed raw objects)."""
    conn = get_db()
    try:
        if source:
            rows = conn.execute("""
                SELECT ao.*, ar.source, ar.retrieved_at
                FROM artifact_object ao
                JOIN artifact_receipt ar ON ao.sha256 = ar.sha256
                WHERE ar.source = ?
                ORDER BY ao.first_seen DESC LIMIT ?
            """, (source, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM artifact_object ORDER BY first_seen DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


# ── Collector Status ────────────────────────────────────────────

@app.get("/collectors")
def collectors() -> list[dict]:
    """Get status of all collectors."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT cs.source, cs.last_run, cs.status, cs.rows, cs.runs,
                   ir.started_at as last_ingest_started,
                   ir.completed_at as last_ingest_completed,
                   ir.records_seen as last_records_seen,
                   ir.error_message as last_error
            FROM collector_state cs
            LEFT JOIN ingest_run ir ON cs.source = ir.source
                AND ir.run_id = (SELECT MAX(run_id) FROM ingest_run WHERE source = cs.source)
            ORDER BY cs.source
        """).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


# ── Summary ─────────────────────────────────────────────────────

@app.get("/summary")
def summary() -> dict:
    """System summary — all key stats in one call."""
    conn = get_db()
    try:
        stats = {}
        for table in ["price_daily", "insider_deals", "short_interest",
                       "rns_announcements", "company_profiles", "observation",
                       "ingest_run", "artifact_object"]:
            stats[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        tickers_with_prices = conn.execute(
            "SELECT COUNT(DISTINCT ticker) FROM price_daily"
        ).fetchone()[0]

        tickers_with_insiders = conn.execute(
            "SELECT COUNT(DISTINCT ticker) FROM insider_deals"
        ).fetchone()[0]

        tickers_with_short = conn.execute(
            "SELECT COUNT(DISTINCT ticker) FROM short_interest WHERE ticker IS NOT NULL"
        ).fetchone()[0]

        return {
            "tables": stats,
            "universe": {
                "total": 25,
                "with_prices": tickers_with_prices,
                "with_insiders": tickers_with_insiders,
                "with_short_interest": tickers_with_short,
            },
            "last_run": row_to_dict(conn.execute(
                "SELECT source, started_at, status FROM ingest_run ORDER BY run_id DESC LIMIT 1"
            ).fetchone()),
            "generated_at": datetime.now().isoformat(),
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8797)
