"""Unified collector runner.

Orchestrates all powstock collectors. Stores results in SQLite.
"""

import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from powstock.universe import UNIVERSE, STOOQ_SYMBOLS

log = logging.getLogger(__name__)


DB_PATH = Path("data/powstock.db")
RAW_DIR = Path("data/raw")


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Initialize SQLite database with required tables."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ingest_run (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            dataset TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT DEFAULT 'running',
            source_url TEXT,
            source_effective_at TEXT,
            retrieved_at TEXT NOT NULL,
            content_sha256 TEXT,
            content_length INTEGER,
            raw_object_uri TEXT,
            parser_version TEXT,
            records_seen INTEGER DEFAULT 0,
            records_accepted INTEGER DEFAULT 0,
            records_rejected INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS raw_artifact (
            artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            mime_type TEXT,
            compression TEXT,
            bytes INTEGER,
            storage_uri TEXT,
            FOREIGN KEY (run_id) REFERENCES ingest_run(run_id)
        );

        CREATE TABLE IF NOT EXISTS raw_ingest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            dataset TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            raw_hash TEXT,
            raw_path TEXT,
            row_count INTEGER,
            bytes INTEGER,
            status TEXT DEFAULT 'ok'
        );

        CREATE TABLE IF NOT EXISTS observation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            ticker TEXT,
            metric TEXT NOT NULL,
            value TEXT NOT NULL,
            unit TEXT,
            event_time TEXT,
            observed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS collector_state (
            source TEXT PRIMARY KEY,
            last_run TEXT,
            status TEXT,
            rows INTEGER DEFAULT 0,
            interval INTEGER,
            runs INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS price_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            UNIQUE(ticker, date)
        );

        CREATE TABLE IF NOT EXISTS insider_deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE,
            ticker TEXT NOT NULL,
            company TEXT,
            director TEXT,
            position TEXT,
            action TEXT,
            price REAL,
            shares INTEGER,
            value REAL,
            effective_at TEXT,
            published_at TEXT,
            observed_at TEXT NOT NULL,
            source_url TEXT,
            UNIQUE(ticker, director, effective_at, action, source_url)
        );

        CREATE TABLE IF NOT EXISTS short_interest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isin TEXT,
            ticker TEXT,
            company TEXT,
            position_pct REAL,
            notional_gbp REAL,
            effective_at TEXT,
            observed_at TEXT NOT NULL,
            UNIQUE(isin, effective_at)
        );

        CREATE TABLE IF NOT EXISTS rns_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE,
            ticker TEXT NOT NULL,
            headline TEXT,
            category TEXT,
            effective_at TEXT,
            published_at TEXT,
            observed_at TEXT NOT NULL,
            source_url TEXT,
            UNIQUE(ticker, source_url)
        );

        CREATE TABLE IF NOT EXISTS company_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            company_number TEXT,
            company_name TEXT,
            status TEXT,
            sic_codes TEXT,
            registered_office TEXT,
            officers_count INTEGER,
            charges_count INTEGER,
            psc_count INTEGER,
            observed_at TEXT NOT NULL,
            UNIQUE(ticker, company_number)
        );
    """)

    conn.commit()
    return conn


def _store_raw(conn: sqlite3.Connection, source: str, dataset: str, data: Any) -> Path:
    """Store raw data to disk and record in database.

    Records both the legacy raw_ingest row and the new ingest_run + raw_artifact
    for proper provenance tracking.
    """
    import hashlib as _hashlib

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = RAW_DIR / f"{source}_{dataset}_{timestamp}.json"

    with open(raw_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

    raw_bytes = raw_path.read_bytes()
    raw_hash = _hashlib.sha256(raw_bytes).hexdigest()
    row_count = len(data) if isinstance(data, (list, dict)) else 1
    now = datetime.now().isoformat()

    # New ingestion ledger
    cursor = conn.execute(
        """INSERT INTO ingest_run
           (source, dataset, started_at, completed_at, status,
            retrieved_at, content_sha256, content_length, raw_object_uri,
            records_seen, records_accepted)
           VALUES (?, ?, ?, ?, 'ok', ?, ?, ?, ?, ?, ?)""",
        (source, dataset, now, now, now, raw_hash, len(raw_bytes),
         str(raw_path), row_count, row_count),
    )
    run_id = cursor.lastrowid

    conn.execute(
        """INSERT INTO raw_artifact
           (run_id, sha256, bytes, storage_uri)
           VALUES (?, ?, ?, ?)""",
        (run_id, raw_hash, len(raw_bytes), str(raw_path)),
    )

    # Legacy table (kept for backwards compat)
    conn.execute(
        "INSERT INTO raw_ingest (source, dataset, observed_at, raw_hash, raw_path, row_count, bytes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (source, dataset, now, raw_hash, str(raw_path), row_count, len(raw_bytes)),
    )

    return raw_path


def _store_obs(conn: sqlite3.Connection, source: str, ticker: str, metric: str, value: Any, unit: str = ""):
    """Store an observation metric."""
    conn.execute(
        "INSERT INTO observation (source, ticker, metric, value, unit, observed_at) VALUES (?, ?, ?, ?, ?, ?)",
        (source, ticker, metric, json.dumps(value, default=str), unit, datetime.now().isoformat()),
    )


def run_prices(conn: sqlite3.Connection) -> int:
    """Run Yahoo Finance price collector for all universe tickers."""
    from powstock.collectors.yahoo_prices import fetch_all_latest

    print("Fetching prices from Yahoo Finance...")
    prices = fetch_all_latest()
    count = 0

    for ticker, data in prices.items():
        conn.execute(
            "INSERT OR REPLACE INTO price_daily (ticker, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ticker, data["asof"], data["open"], data["high"], data["low"], data["price"], data["volume"]),
        )
        _store_obs(conn, "stooq", ticker, "price", data["price"], "GBP")
        _store_obs(conn, "stooq", ticker, "pct_1d", data["pct_1d"], "percent")
        count += 1

    _store_raw(conn, "stooq", "prices", prices)
    conn.execute(
        "INSERT OR REPLACE INTO collector_state (source, last_run, status, rows, runs) VALUES (?, ?, 'ok', ?, COALESCE((SELECT runs FROM collector_state WHERE source='stooq'), 0) + 1)",
        ("stooq", datetime.now().isoformat(), count),
    )

    print(f"  Prices: {count} tickers updated")
    return count


def run_insiders(conn: sqlite3.Connection) -> int:
    """Run FCA PDMR insider dealing collector for universe tickers."""
    from powstock.collectors.fca_pdmr import fetch_pdmr_announcements

    print("Fetching insider dealings from Investegate...")
    # Fetch all recent PDMR announcements (not per-ticker to avoid duplicates)
    deals = fetch_pdmr_announcements(max_pages=5)
    count = 0

    for deal in deals:
        try:
            # Deterministic event_id for idempotent inserts
            import hashlib as _hl
            event_id = _hl.sha256(
                f"{deal['ticker']}|{deal['director']}|{deal['trade_date']}|"
                f"{deal['transaction_type']}|{deal.get('url', '')}".encode()
            ).hexdigest()[:16]

            conn.execute(
                """INSERT OR REPLACE INTO insider_deals
                   (event_id, ticker, company, director, position, action, price, shares, value,
                    effective_at, published_at, observed_at, source_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, deal["ticker"], deal["company"], deal["director"],
                 deal["position"], deal["transaction_type"], deal["price"],
                 deal["shares"], deal["total_value"],
                 deal["trade_date"], deal.get("filing_date", ""),
                 datetime.now().isoformat(), deal.get("url", "")),
            )
            _store_obs(conn, "investegate", deal["ticker"], "insider_deal", deal["transaction_type"])
            count += 1
        except Exception as e:
            log.warning("PDMR insert failed for %s: %s", deal.get("ticker", "?"), e)

    _store_raw(conn, "fca_pdmr", "notifications", {"count": count})
    conn.execute(
        "INSERT OR REPLACE INTO collector_state (source, last_run, status, rows, runs) VALUES (?, ?, 'ok', ?, COALESCE((SELECT runs FROM collector_state WHERE source='fca_pdmr'), 0) + 1)",
        ("fca_pdmr", datetime.now().isoformat(), count),
    )

    print(f"  Insiders: {count} deals found")
    return count


def run_short_interest(conn: sqlite3.Connection) -> int:
    """Run FCA short interest collector."""
    from powstock.collectors.fca_short_interest import fetch_current_short_positions

    print("Fetching short interest from FCA...")
    positions = fetch_current_short_positions()
    count = 0

    for pos in positions:
        # Try to match to universe via ISIN (exact match preferred)
        ticker = None
        for security in UNIVERSE:
            if security.isin and security.isin.upper() == pos.isin.upper():
                ticker = security.ticker
                break

        # Fallback: exact company name match (not substring)
        if ticker is None:
            for security in UNIVERSE:
                if security.company.upper() == pos.issuer_name.upper():
                    ticker = security.ticker
                    break

        conn.execute(
            """INSERT OR REPLACE INTO short_interest
               (isin, ticker, company, position_pct, notional_gbp, effective_at, observed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pos.isin, ticker, pos.issuer_name, pos.position_pct,
             pos.notional_value_gbp, pos.report_date, datetime.now().isoformat()),
        )
        if ticker:
            _store_obs(conn, "fca_ansp", ticker, "short_pct", pos.position_pct, "percent")
        count += 1

    _store_raw(conn, "fca_ansp", "short_positions", {"count": count})
    conn.execute(
        "INSERT OR REPLACE INTO collector_state (source, last_run, status, rows, runs) VALUES (?, ?, 'ok', ?, COALESCE((SELECT runs FROM collector_state WHERE source='fca_ansp'), 0) + 1)",
        ("fca_ansp", datetime.now().isoformat(), count),
    )

    print(f"  Short interest: {count} positions")
    return count


def run_rns(conn: sqlite3.Connection) -> int:
    """Run RNS announcement collector for universe tickers."""
    from powstock.collectors.rns_announcements import fetch_ticker_rns

    print("Fetching RNS announcements...")
    count = 0

    for security in UNIVERSE:
        try:
            announcements = fetch_ticker_rns(security.ticker, max_pages=2)
            for ann in announcements:
                # Deterministic event_id
                import hashlib as _hl
                event_id = _hl.sha256(
                    f"{ann['ticker']}|{ann['source_url']}".encode()
                ).hexdigest()[:16]

                conn.execute(
                    """INSERT OR REPLACE INTO rns_announcements
                       (event_id, ticker, headline, category, effective_at, published_at,
                        observed_at, source_url)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (event_id, ann["ticker"], ann["headline"], ann["category"],
                     ann["published_at"], ann["published_at"],
                     datetime.now().isoformat(), ann["source_url"]),
                )
                _store_obs(conn, "investegate", ann["ticker"], "rns_announcement", ann["headline"][:100])
                count += 1

            time.sleep(1)
        except Exception as e:
            log.warning("RNS fetch failed for %s: %s", security.ticker, e)

    _store_raw(conn, "lse_rns", "announcements", {"count": count})
    conn.execute(
        "INSERT OR REPLACE INTO collector_state (source, last_run, status, rows, runs) VALUES (?, ?, 'ok', ?, COALESCE((SELECT runs FROM collector_state WHERE source='lse_rns'), 0) + 1)",
        ("lse_rns", datetime.now().isoformat(), count),
    )

    print(f"  RNS: {count} announcements")
    return count


def run_companies(conn: sqlite3.Connection) -> int:
    """Run Companies House collector for universe tickers."""
    from powstock.collectors.companies_house import fetch_universe_companies

    print("Fetching company data from Companies House...")
    companies = fetch_universe_companies()
    count = 0

    for ticker, data in companies.items():
        conn.execute(
            """INSERT OR REPLACE INTO company_profiles
               (ticker, company_number, company_name, status, sic_codes, registered_office,
                officers_count, charges_count, psc_count, observed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, data["company_number"], data["company_name"], data["status"],
             json.dumps(data["sic_codes"]), data["registered_office"],
             data["officers_count"], data["charges_count"], data["psc_count"],
             datetime.now().isoformat()),
        )
        _store_obs(conn, "companies_house", ticker, "officers_count", data["officers_count"])
        _store_obs(conn, "companies_house", ticker, "charges_count", data["charges_count"])
        count += 1

    _store_raw(conn, "companies_house", "profiles", companies)
    conn.execute(
        "INSERT OR REPLACE INTO collector_state (source, last_run, status, rows, runs) VALUES (?, ?, 'ok', ?, COALESCE((SELECT runs FROM collector_state WHERE source='companies_house'), 0) + 1)",
        ("companies_house", datetime.now().isoformat(), count),
    )

    print(f"  Companies: {count} profiles")
    return count


def run_finnhub(conn: sqlite3.Connection) -> int:
    """Run Finnhub insider collector (optional, requires API key)."""
    from powstock.settings import get_settings
    api_key = get_settings().llm_api_key  # reuse a key slot or add FINNHUB_API_KEY
    if not api_key:
        log.info("Finnhub: no API key configured, skipping")
        return 0

    from powstock.collectors.finnhub import fetch_universe_insiders

    print("Fetching insider transactions from Finnhub...")
    results = fetch_universe_insiders(api_key=api_key)
    count = sum(len(v) for v in results.values())

    _store_raw(conn, "finnhub", "insider_transactions", results)
    conn.execute(
        "INSERT OR REPLACE INTO collector_state (source, last_run, status, rows, runs) VALUES (?, ?, 'ok', ?, COALESCE((SELECT runs FROM collector_state WHERE source='finnhub'), 0) + 1)",
        ("finnhub", datetime.now().isoformat(), count),
    )

    print(f"  Finnhub: {count} transactions")
    return count


def run_all(conn: sqlite3.Connection | None = None) -> dict[str, int]:
    """Run all collectors in sequence.

    Returns: {collector_name: rows_collected}
    """
    should_close = conn is None
    if conn is None:
        conn = init_db()

    print(f"\n{'='*60}")
    print(f"POWSTOCK Collector Run — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    results = {}

    # Run collectors (prices first, then others)
    try:
        results["prices"] = run_prices(conn)
    except Exception as e:
        log.error("prices collector failed: %s", e)
        results["prices"] = 0

    try:
        results["insiders"] = run_insiders(conn)
    except Exception as e:
        log.error("insiders collector failed: %s", e)
        results["insiders"] = 0

    try:
        results["short_interest"] = run_short_interest(conn)
    except Exception as e:
        log.error("short_interest collector failed: %s", e)
        results["short_interest"] = 0

    try:
        results["rns"] = run_rns(conn)
    except Exception as e:
        log.error("rns collector failed: %s", e)
        results["rns"] = 0

    try:
        results["companies"] = run_companies(conn)
    except Exception as e:
        log.error("companies collector failed: %s", e)
        results["companies"] = 0

    # Optional collectors (require API keys)
    try:
        results["finnhub"] = run_finnhub(conn)
    except Exception as e:
        log.error("finnhub collector failed: %s", e)
        results["finnhub"] = 0

    conn.commit()

    print(f"\n{'='*60}")
    print("Summary:")
    for name, count in results.items():
        print(f"  {name}: {count}")
    print(f"{'='*60}\n")

    if should_close:
        conn.close()

    return results


def status(conn: sqlite3.Connection | None = None) -> None:
    """Print collector status."""
    should_close = conn is None
    if conn is None:
        conn = init_db()

    print("\nCollector Status:")
    print("-" * 60)

    rows = conn.execute("SELECT source, last_run, status, rows, runs FROM collector_state ORDER BY source").fetchall()
    if not rows:
        print("  No collectors have run yet.")
    else:
        for source, last_run, status_val, rows_count, runs in rows:
            print(f"  {source:20s} | last: {last_run or 'never':20s} | status: {status_val or 'unknown':6s} | rows: {rows_count:5d} | runs: {runs}")

    # Table row counts
    print("\nTable Row Counts:")
    print("-" * 60)
    for table in ["price_daily", "insider_deals", "short_interest", "rns_announcements",
                   "company_profiles", "ingest_run", "raw_artifact"]:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:25s} | {count:6d} rows")
        except Exception:
            print(f"  {table:25s} | (not created)")

    if should_close:
        conn.close()
