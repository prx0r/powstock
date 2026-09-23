"""powstock MCP server — exposes all data via MCP tools.

powops and other agents can query powstock data through MCP.

Usage:
    python -m powstock.mcp
    # or via stdio for MCP integration
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path("data/powstock.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


# ── Tool implementations ────────────────────────────────────────

def powstock_health() -> dict:
    """System health check — tables, last run, heartbeat."""
    conn = get_db()
    try:
        tables = {}
        for table in ["price_daily", "insider_deals", "short_interest",
                       "rns_announcements", "company_profiles", "ingest_run"]:
            tables[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        last_run = row_to_dict(conn.execute(
            "SELECT source, started_at, status, records_seen FROM ingest_run ORDER BY run_id DESC LIMIT 1"
        ).fetchone())

        hb_path = Path("data/heartbeat.json")
        heartbeat = json.loads(hb_path.read_text()) if hb_path.exists() else None

        return {
            "status": "ok",
            "tables": tables,
            "last_run": last_run,
            "heartbeat": heartbeat,
        }
    finally:
        conn.close()


def powstock_universe() -> list[dict]:
    """List all 25 universe securities."""
    from powstock.universe import UNIVERSE
    return [
        {"ticker": s.ticker, "company": s.company, "isin": s.isin}
        for s in UNIVERSE
    ]


def powstock_prices(ticker: str = "", days: int = 30) -> list[dict]:
    """Get price history. Empty ticker = all tickers latest."""
    conn = get_db()
    try:
        if ticker:
            rows = conn.execute(
                "SELECT ticker, date, open, high, low, close, volume FROM price_daily WHERE ticker = ? ORDER BY date DESC LIMIT ?",
                (ticker.upper(), days),
            ).fetchall()
        else:
            rows = conn.execute("""
                SELECT p.ticker, p.date, p.open, p.high, p.low, p.close, p.volume
                FROM price_daily p
                INNER JOIN (SELECT ticker, MAX(date) as max_date FROM price_daily GROUP BY ticker) m
                ON p.ticker = m.ticker AND p.date = m.max_date
                ORDER BY p.ticker
            """).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


def powstock_insiders(ticker: str = "", limit: int = 50) -> list[dict]:
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


def powstock_short_interest(ticker: str = "", limit: int = 50) -> list[dict]:
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


def powstock_rns(ticker: str = "", limit: int = 50) -> list[dict]:
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


def powstock_companies(ticker: str = "") -> list[dict]:
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


def powstock_signals(ticker: str) -> dict:
    """Compute all signals for a ticker."""
    conn = get_db()
    try:
        from layer2.signals import compute_all_signals
        results = compute_all_signals(conn, [ticker.upper()])
        return {"ticker": ticker.upper(), "signals": [
            {"name": s.name, "value": s.value, "confidence": s.confidence, "metadata": s.metadata}
            for s in results
        ]}
    finally:
        conn.close()


def powstock_runs(limit: int = 10) -> list[dict]:
    """Get recent ingest runs."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT source, started_at, completed_at, status, records_seen, error_message FROM ingest_run ORDER BY run_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


def powstock_collectors() -> list[dict]:
    """Get status of all collectors."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT source, last_run, status, rows, runs
            FROM collector_state ORDER BY source
        """).fetchall()
        return rows_to_list(rows)
    finally:
        conn.close()


def powstock_summary() -> dict:
    """System summary — all key stats."""
    conn = get_db()
    try:
        stats = {}
        for table in ["price_daily", "insider_deals", "short_interest",
                       "rns_announcements", "company_profiles"]:
            stats[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        return {
            "tables": stats,
            "universe_size": 25,
            "tickers_with_prices": conn.execute("SELECT COUNT(DISTINCT ticker) FROM price_daily").fetchone()[0],
            "tickers_with_insiders": conn.execute("SELECT COUNT(DISTINCT ticker) FROM insider_deals").fetchone()[0],
            "tickers_with_short": conn.execute("SELECT COUNT(DISTINCT ticker) FROM short_interest WHERE ticker IS NOT NULL").fetchone()[0],
        }
    finally:
        conn.close()


# ── MCP Server ──────────────────────────────────────────────────

TOOLS = [
    {
        "name": "powstock_health",
        "description": "System health check — tables, last run, heartbeat",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "powstock_universe",
        "description": "List all 25 universe securities with tickers, companies, ISINs",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "powstock_prices",
        "description": "Get price history. Pass ticker for specific, empty for all latest.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Ticker symbol (e.g. NG.)"},
                "days": {"type": "integer", "description": "Days of history", "default": 30},
            },
        },
    },
    {
        "name": "powstock_insiders",
        "description": "Get insider dealing transactions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Filter by ticker"},
                "limit": {"type": "integer", "description": "Max results", "default": 50},
            },
        },
    },
    {
        "name": "powstock_short_interest",
        "description": "Get FCA short interest positions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Filter by ticker"},
                "limit": {"type": "integer", "description": "Max results", "default": 50},
            },
        },
    },
    {
        "name": "powstock_rns",
        "description": "Get RNS announcements",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Filter by ticker"},
                "limit": {"type": "integer", "description": "Max results", "default": 50},
            },
        },
    },
    {
        "name": "powstock_companies",
        "description": "Get company profiles",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Filter by ticker"},
            },
        },
    },
    {
        "name": "powstock_signals",
        "description": "Compute all signals for a ticker (momentum, short interest, composite, etc.)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Ticker symbol"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "powstock_runs",
        "description": "Get recent ingest runs (collection history)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results", "default": 10},
            },
        },
    },
    {
        "name": "powstock_collectors",
        "description": "Get status of all collectors",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "powstock_summary",
        "description": "System summary — table counts, universe coverage",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_tool(name: str, arguments: dict) -> Any:
    """Route MCP tool call to implementation."""
    dispatch = {
        "powstock_health": lambda: powstock_health(),
        "powstock_universe": lambda: powstock_universe(),
        "powstock_prices": lambda: powstock_prices(arguments.get("ticker", ""), arguments.get("days", 30)),
        "powstock_insiders": lambda: powstock_insiders(arguments.get("ticker", ""), arguments.get("limit", 50)),
        "powstock_short_interest": lambda: powstock_short_interest(arguments.get("ticker", ""), arguments.get("limit", 50)),
        "powstock_rns": lambda: powstock_rns(arguments.get("ticker", ""), arguments.get("limit", 50)),
        "powstock_companies": lambda: powstock_companies(arguments.get("ticker", "")),
        "powstock_signals": lambda: powstock_signals(arguments["ticker"]),
        "powstock_runs": lambda: powstock_runs(arguments.get("limit", 10)),
        "powstock_collectors": lambda: powstock_collectors(),
        "powstock_summary": lambda: powstock_summary(),
    }
    func = dispatch.get(name)
    if func:
        return func()
    return {"error": f"Unknown tool: {name}"}


# ── stdio MCP server ────────────────────────────────────────────

def run_stdio():
    """Run MCP server over stdio (for MCP integration)."""
    import sys
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            method = request.get("method", "")
            req_id = request.get("id")
            params = request.get("params", {})

            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "powstock", "version": "0.1.0"},
                    },
                }
            elif method == "tools/list":
                response = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
            elif method == "tools/call":
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})
                result = handle_tool(tool_name, arguments)
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result, default=str, indent=2)}]
                    },
                }
            else:
                response = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}

            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except Exception as e:
            error_response = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    import sys
    if "--stdio" in sys.argv:
        run_stdio()
    else:
        print("powstock MCP server")
        print("Tools available:")
        for tool in TOOLS:
            print(f"  - {tool['name']}: {tool['description']}")
        print()
        print("Usage: python -m powstock.mcp --stdio")
