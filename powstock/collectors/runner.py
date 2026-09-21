"""Unified collector runner.

Orchestrates all powstock collectors. Stores results in SQLite.
Uses ArtifactStore for raw bytes, not parsed objects.
Uses collector registry for manifest-driven execution.
"""

import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from powstock.universe import UNIVERSE, STOOQ_SYMBOLS
from layer1.artifacts import ArtifactStore, IngestRun, PARSER_VERSION
from layer1.registry import get_enabled, print_registry

log = logging.getLogger(__name__)


DB_PATH = Path("data/powstock.db")
RAW_DIR = Path("data/raw")


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Initialize SQLite database with required tables.

    Schema version: 2 (artifact_object + artifact_receipt, foreign keys enforced).
    """
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        -- ============================================================
        -- Level 1: Ingest lifecycle
        -- ============================================================

        CREATE TABLE IF NOT EXISTS ingest_run (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            dataset TEXT NOT NULL DEFAULT '',
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT DEFAULT 'running',
            source_url TEXT DEFAULT '',
            parser_version TEXT DEFAULT '1',
            content_sha256 TEXT,
            content_length INTEGER,
            raw_object_uri TEXT,
            records_seen INTEGER DEFAULT 0,
            records_accepted INTEGER DEFAULT 0,
            records_rejected INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            error_message TEXT
        );

        -- ============================================================
        -- Level 1: Content-addressed objects + receipts
        -- ============================================================

        CREATE TABLE IF NOT EXISTS artifact_object (
            sha256 TEXT PRIMARY KEY,
            bytes INTEGER NOT NULL,
            content_type TEXT DEFAULT 'application/octet-stream',
            storage_uri TEXT NOT NULL,
            first_seen TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS artifact_receipt (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sha256 TEXT NOT NULL,
            run_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            dataset TEXT DEFAULT '',
            storage_uri TEXT NOT NULL,
            bytes INTEGER NOT NULL,
            retrieved_at TEXT NOT NULL,
            FOREIGN KEY (sha256) REFERENCES artifact_object(sha256),
            FOREIGN KEY (run_id) REFERENCES ingest_run(run_id)
        );

        CREATE INDEX IF NOT EXISTS idx_receipt_source ON artifact_receipt(source);
        CREATE INDEX IF NOT EXISTS idx_receipt_run ON artifact_receipt(run_id);

        -- ============================================================
        -- Level 1: Normalized facts (every fact has provenance)
        -- ============================================================

        CREATE TABLE IF NOT EXISTS price_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            source_id TEXT DEFAULT 'yahoo_finance',
            artifact_id TEXT,
            parser_version TEXT DEFAULT '1',
            observed_at TEXT NOT NULL,
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
            group_shares INTEGER,
            group_value REAL,
            parse_status TEXT DEFAULT 'complete',
            source_id TEXT DEFAULT 'investegate',
            artifact_id TEXT,
            parser_version TEXT DEFAULT '1',
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
            source_id TEXT DEFAULT 'fca_ansp',
            artifact_id TEXT,
            parser_version TEXT DEFAULT '1',
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
            source_id TEXT DEFAULT 'investegate',
            artifact_id TEXT,
            parser_version TEXT DEFAULT '1',
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
            source_id TEXT DEFAULT 'companies_house',
            artifact_id TEXT,
            parser_version TEXT DEFAULT '1',
            UNIQUE(ticker, company_number)
        );

        -- ============================================================
        -- Level 1: Source coverage tracking
        -- ============================================================

        CREATE TABLE IF NOT EXISTS source_coverage (
            source_id TEXT PRIMARY KEY,
            coverage_start TEXT,
            coverage_end TEXT,
            expected_periods TEXT DEFAULT '{}',
            observed_periods TEXT DEFAULT '{}',
            missing_periods TEXT DEFAULT '[]',
            continuity_pct REAL DEFAULT 0.0,
            last_checked_at TEXT,
            status TEXT DEFAULT 'never_run'
        );

        -- ============================================================
        -- Level 1: Collector state (legacy, kept for backwards compat)
        -- ============================================================

        CREATE TABLE IF NOT EXISTS collector_state (
            source TEXT PRIMARY KEY,
            last_run TEXT,
            status TEXT,
            rows INTEGER DEFAULT 0,
            interval INTEGER,
            runs INTEGER DEFAULT 0
        );

        -- ============================================================
        -- Level 1: Observations (raw metrics)
        -- ============================================================

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
    """)

    conn.commit()
    return conn


def _store_obs(conn: sqlite3.Connection, source: str, ticker: str, metric: str, value: Any, unit: str = ""):
    """Store an observation metric."""
    conn.execute(
        "INSERT INTO observation (source, ticker, metric, value, unit, observed_at) VALUES (?, ?, ?, ?, ?, ?)",
        (source, ticker, metric, json.dumps(value, default=str), unit, datetime.now().isoformat()),
    )


def run_prices(conn: sqlite3.Connection, artifact_store: ArtifactStore | None = None) -> int:
    """Run Yahoo Finance price collector for all universe tickers.

    Stores raw HTTP response bytes, then parses to price_daily facts.
    """
    from powstock.collectors.yahoo_prices import fetch_all_latest

    print("Fetching prices from Yahoo Finance...")

    with IngestRun(conn, source="yahoo_finance", dataset="latest_prices",
                   source_url="https://query1.finance.yahoo.com/v8/finance/chart") as run:
        prices = fetch_all_latest()
        count = 0

        # Store raw JSON as artifact (this is the provider response, not our normalization)
        if artifact_store and prices:
            raw_bytes = json.dumps(prices, indent=2, default=str).encode()
            artifact = artifact_store.put_http_response(
                content=raw_bytes,
                source="yahoo_finance",
                dataset="latest_prices",
                run_id=run.id,
                source_url="https://query1.finance.yahoo.com/v8/finance/chart",
            )
            run.link_artifact(artifact["sha256"], artifact["storage_uri"], artifact["bytes"])

        for ticker, data in prices.items():
            conn.execute(
                "INSERT OR REPLACE INTO price_daily (ticker, date, open, high, low, close, volume, source_id, artifact_id, parser_version, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ticker, data["asof"], data["open"], data["high"], data["low"], data["price"], data["volume"],
                 "yahoo_finance", artifact.get("sha256") if artifact else None,
                 PARSER_VERSION, datetime.now().isoformat()),
            )
            _store_obs(conn, "yahoo_finance", ticker, "price", data["price"], "GBP")
            _store_obs(conn, "yahoo_finance", ticker, "pct_1d", data["pct_1d"], "percent")
            count += 1

        conn.execute(
            "INSERT OR REPLACE INTO collector_state (source, last_run, status, rows, runs) VALUES (?, ?, 'ok', ?, COALESCE((SELECT runs FROM collector_state WHERE source='yahoo_finance'), 0) + 1)",
            ("yahoo_finance", datetime.now().isoformat(), count),
        )

        run.complete(records_seen=count, records_accepted=count)

    print(f"  Prices: {count} tickers updated")
    return count


def run_insiders(conn: sqlite3.Connection, artifact_store: ArtifactStore | None = None) -> int:
    """Run FCA PDMR insider dealing collector for universe tickers."""
    from powstock.collectors.fca_pdmr import fetch_pdmr_announcements

    print("Fetching insider dealings from Investegate...")

    with IngestRun(conn, source="investegate_pdmr", dataset="notification_html",
                   source_url="https://www.investegate.co.uk") as run:
        deals, raw_artifacts = fetch_pdmr_announcements(max_pages=5)

        # Store raw HTML artifacts
        if artifact_store and raw_artifacts:
            for art in raw_artifacts:
                artifact_store.put_http_response(
                    content=art["content"],
                    source="investegate_pdmr",
                    dataset="notification_html",
                    run_id=run.id,
                    source_url=art["source_url"],
                    metadata={"ticker": art["ticker"]},
                )

        count = 0
        for deal in deals:
            try:
                import hashlib as _hl
                event_id = _hl.sha256(
                    f"{deal['ticker']}|{deal['director']}|{deal['trade_date']}|"
                    f"{deal['transaction_type']}|{deal.get('url', '')}".encode()
                ).hexdigest()[:16]

                conn.execute(
                    """INSERT OR REPLACE INTO insider_deals
                       (event_id, ticker, company, director, position, action, price, shares, value,
                        effective_at, published_at, source_url,
                        group_shares, group_value, parse_status,
                        source_id, artifact_id, parser_version, observed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (event_id, deal["ticker"], deal["company"], deal["director"],
                     deal["position"], deal["transaction_type"], deal["price"],
                     deal["shares"], deal["total_value"],
                     deal["trade_date"], deal.get("filing_date", ""),
                     deal.get("url", ""),
                     deal.get("group_shares"), deal.get("group_value"),
                     deal.get("parse_status", "complete"),
                     "investegate_pdmr", None, PARSER_VERSION,
                     datetime.now().isoformat()),
                )
                _store_obs(conn, "investegate_pdmr", deal["ticker"], "insider_deal", deal["transaction_type"])
                count += 1
            except Exception as e:
                log.warning("PDMR insert failed for %s: %s", deal.get("ticker", "?"), e)

        conn.execute(
            "INSERT OR REPLACE INTO collector_state (source, last_run, status, rows, runs) VALUES (?, ?, 'ok', ?, COALESCE((SELECT runs FROM collector_state WHERE source='investegate_pdmr'), 0) + 1)",
            ("investegate_pdmr", datetime.now().isoformat(), count),
        )

        run.complete(records_seen=len(deals), records_accepted=count)

    print(f"  Insiders: {count} deals found")
    return count


def run_short_interest(conn: sqlite3.Connection, artifact_store: ArtifactStore | None = None) -> int:
    """Run FCA short interest collector."""
    from powstock.collectors.fca_short_interest import fetch_current_short_positions

    print("Fetching short interest from FCA...")

    with IngestRun(conn, source="fca_ansp", dataset="short_positions_xlsx",
                   source_url="https://www.fca.org.uk/publication/documents/aggregated-net-short-positions.xlsx") as run:
        positions, raw_bytes = fetch_current_short_positions()

        # Store raw XLSX artifact
        if artifact_store and raw_bytes:
            artifact = artifact_store.put_bytes(
                data=raw_bytes,
                source="fca_ansp",
                dataset="short_positions_xlsx",
                run_id=run.id,
                source_url="https://www.fca.org.uk/publication/documents/aggregated-net-short-positions.xlsx",
            )
            run.link_artifact(artifact["sha256"], artifact["storage_uri"], artifact["bytes"])

        count = 0
        for pos in positions:
            ticker = None
            for security in UNIVERSE:
                if security.isin and security.isin.upper() == pos.isin.upper():
                    ticker = security.ticker
                    break
            if ticker is None:
                for security in UNIVERSE:
                    if security.company.upper() == pos.issuer_name.upper():
                        ticker = security.ticker
                        break

            conn.execute(
                """INSERT OR REPLACE INTO short_interest
                   (isin, ticker, company, position_pct, notional_gbp, effective_at, observed_at,
                    source_id, artifact_id, parser_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pos.isin, ticker, pos.issuer_name, pos.position_pct,
                 pos.notional_value_gbp, pos.report_date, datetime.now().isoformat(),
                 "fca_ansp", artifact.get("sha256") if artifact else None,
                 PARSER_VERSION),
            )
            if ticker:
                _store_obs(conn, "fca_ansp", ticker, "short_pct", pos.position_pct, "percent")
            count += 1

        conn.execute(
            "INSERT OR REPLACE INTO collector_state (source, last_run, status, rows, runs) VALUES (?, ?, 'ok', ?, COALESCE((SELECT runs FROM collector_state WHERE source='fca_ansp'), 0) + 1)",
            ("fca_ansp", datetime.now().isoformat(), count),
        )

        run.complete(records_seen=len(positions), records_accepted=count)

    print(f"  Short interest: {count} positions")
    return count


def run_rns(conn: sqlite3.Connection, artifact_store: ArtifactStore | None = None) -> int:
    """Run RNS announcement collector for universe tickers.

    Uses Investegate direct company pages (one per ticker).
    """
    from powstock.collectors.rns_announcements import fetch_investegate_page, _parse_investegate_html
    from powstock.universe import UNIVERSE

    print("Fetching RNS announcements...")
    count = 0

    with IngestRun(conn, source="investegate_rns", dataset="company_pages",
                   source_url="https://www.investegate.co.uk") as run:
        for security in UNIVERSE:
            try:
                html = fetch_investegate_page(ticker=security.ticker, page=1)
                if artifact_store and html:
                    artifact = artifact_store.put_bytes(
                        data=html.encode(),
                        source="investegate_rns",
                        dataset=f"company_{security.ticker}",
                        run_id=run.id,
                        source_url=f"https://www.investegate.co.uk/company/{security.ticker}",
                        metadata={"ticker": security.ticker},
                    )

                announcements = _parse_investegate_html(html, ticker_filter=security.ticker)
                for ann in announcements:
                    import hashlib as _hl
                    event_id = _hl.sha256(
                        f"{security.ticker}|{ann.source_url}".encode()
                    ).hexdigest()[:16]

                    conn.execute(
                        """INSERT OR REPLACE INTO rns_announcements
                           (event_id, ticker, headline, category, effective_at, published_at,
                            observed_at, source_url, source_id, artifact_id, parser_version)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (event_id, security.ticker, ann.headline, ann.category,
                         ann.published_at, ann.published_at,
                         datetime.now().isoformat(), ann.source_url,
                         "investegate_rns", artifact.get("sha256") if artifact else None,
                         PARSER_VERSION),
                    )
                    _store_obs(conn, "investegate_rns", security.ticker, "rns_announcement", ann.headline[:100])
                    count += 1

                time.sleep(0.5)
            except Exception as e:
                log.warning("RNS fetch failed for %s: %s", security.ticker, e)

        conn.execute(
            "INSERT OR REPLACE INTO collector_state (source, last_run, status, rows, runs) VALUES (?, ?, 'ok', ?, COALESCE((SELECT runs FROM collector_state WHERE source='investegate_rns'), 0) + 1)",
            ("investegate_rns", datetime.now().isoformat(), count),
        )

        run.complete(records_seen=count, records_accepted=count)

    print(f"  RNS: {count} announcements")
    return count


def run_companies(conn: sqlite3.Connection, artifact_store: ArtifactStore | None = None) -> int:
    """Run Companies House collector for universe tickers."""
    from powstock.collectors.companies_house import fetch_universe_companies

    print("Fetching company data from Companies House...")

    with IngestRun(conn, source="companies_house", dataset="universe_profiles",
                   source_url="https://api.company-information.service.gov.uk") as run:
        companies = fetch_universe_companies()
        count = 0

        for ticker, data in companies.items():
            conn.execute(
                """INSERT OR REPLACE INTO company_profiles
                   (ticker, company_number, company_name, status, sic_codes, registered_office,
                    officers_count, charges_count, psc_count, observed_at,
                    source_id, parser_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ticker, data["company_number"], data["company_name"], data["status"],
                 json.dumps(data["sic_codes"]), data["registered_office"],
                 data["officers_count"], data["charges_count"], data["psc_count"],
                 datetime.now().isoformat(),
                 "companies_house", PARSER_VERSION),
            )
            _store_obs(conn, "companies_house", ticker, "officers_count", data["officers_count"])
            _store_obs(conn, "companies_house", ticker, "charges_count", data["charges_count"])
            count += 1

        # Store raw JSON bytes
        if artifact_store and companies:
            raw_bytes = json.dumps(companies, indent=2, default=str).encode()
            artifact = artifact_store.put_bytes(
                data=raw_bytes,
                source="companies_house",
                dataset="universe_profiles",
                run_id=run.id,
                source_url="https://api.company-information.service.gov.uk",
            )
            run.link_artifact(artifact["sha256"], artifact["storage_uri"], artifact["bytes"])

        conn.execute(
            "INSERT OR REPLACE INTO collector_state (source, last_run, status, rows, runs) VALUES (?, ?, 'ok', ?, COALESCE((SELECT runs FROM collector_state WHERE source='companies_house'), 0) + 1)",
            ("companies_house", datetime.now().isoformat(), count),
        )

        run.complete(records_seen=len(companies), records_accepted=count)

    print(f"  Companies: {count} profiles")
    return count


def run_finnhub(conn: sqlite3.Connection, artifact_store: ArtifactStore | None = None) -> int:
    """Run Finnhub insider collector (optional, requires API key)."""
    from powstock.settings import get_settings
    api_key = get_settings().finnhub_api_key
    if not api_key:
        log.info("Finnhub: no API key configured, skipping")
        return 0

    from powstock.collectors.finnhub import fetch_universe_insiders

    print("Fetching insider transactions from Finnhub...")

    with IngestRun(conn, source="finnhub", dataset="insider_transactions",
                   source_url="https://finnhub.io/api/v1") as run:
        results = fetch_universe_insiders(api_key=api_key)
        count = sum(len(v) for v in results.values())

        if artifact_store and results:
            raw_bytes = json.dumps(results, indent=2, default=str).encode()
            artifact = artifact_store.put_bytes(
                data=raw_bytes,
                source="finnhub",
                dataset="insider_transactions",
                run_id=run.id,
                source_url="https://finnhub.io/api/v1",
            )
            run.link_artifact(artifact["sha256"], artifact["storage_uri"], artifact["bytes"])

        conn.execute(
            "INSERT OR REPLACE INTO collector_state (source, last_run, status, rows, runs) VALUES (?, ?, 'ok', ?, COALESCE((SELECT runs FROM collector_state WHERE source='finnhub'), 0) + 1)",
            ("finnhub", datetime.now().isoformat(), count),
        )

        run.complete(records_seen=count, records_accepted=count)

    print(f"  Finnhub: {count} transactions")
    return count


def run_all(conn: sqlite3.Connection | None = None) -> dict[str, int]:
    """Run all collectors in sequence.

    Returns: {collector_name: rows_collected}
    """
    should_close = conn is None
    if conn is None:
        conn = init_db()

    # Create ArtifactStore for raw byte preservation
    artifact_store = ArtifactStore(base_dir=RAW_DIR, conn=conn)

    print(f"\n{'='*60}")
    print(f"POWSTOCK Collector Run — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    results = {}

    # Run collectors (prices first, then others)
    try:
        results["prices"] = run_prices(conn, artifact_store)
    except Exception as e:
        log.error("prices collector failed: %s", e)
        results["prices"] = 0

    try:
        results["insiders"] = run_insiders(conn, artifact_store)
    except Exception as e:
        log.error("insiders collector failed: %s", e)
        results["insiders"] = 0

    try:
        results["short_interest"] = run_short_interest(conn, artifact_store)
    except Exception as e:
        log.error("short_interest collector failed: %s", e)
        results["short_interest"] = 0

    try:
        results["rns"] = run_rns(conn, artifact_store)
    except Exception as e:
        log.error("rns collector failed: %s", e)
        results["rns"] = 0

    try:
        results["companies"] = run_companies(conn, artifact_store)
    except Exception as e:
        log.error("companies collector failed: %s", e)
        results["companies"] = 0

    # Optional collectors (require API keys)
    try:
        results["finnhub"] = run_finnhub(conn, artifact_store)
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

    # Show registry
    print_registry()

    print("Collector Status:")
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
                   "company_profiles", "ingest_run", "artifact_object", "artifact_receipt"]:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:25s} | {count:6d} rows")
        except Exception:
            print(f"  {table:25s} | (not created)")

    # Show artifact summary
    try:
        obj_count = conn.execute("SELECT COUNT(*) FROM artifact_object").fetchone()[0]
        receipt_count = conn.execute("SELECT COUNT(*) FROM artifact_receipt").fetchone()[0]
        print(f"\n  Object store: {obj_count} objects, {receipt_count} receipts")
    except Exception:
        pass

    if should_close:
        conn.close()
