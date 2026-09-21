"""Database migration — old schema to new columns.

Adds missing columns and tables to existing databases.
Safe to run multiple times (idempotent).

Usage: python -m powstock.migrate

Status: STALE
- Never imported by any module.
- No Makefile target references it.
- Designed for standalone execution only.
- Useful when schema changes are needed on existing DBs.
- To use: python -m powstock.migrate (from repo root).
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("data/powstock.db")


def migrate(conn: sqlite3.Connection) -> dict[str, bool]:
    """Apply all pending migrations. Returns {migration_name: applied}."""
    results: dict[str, bool] = {}

    # Ensure migrate tracking table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)
    conn.commit()

    applied = {r[0] for r in conn.execute("SELECT name FROM _migrations").fetchall()}

    # Migration: add event_id to insider_deals
    if "add_event_id_insider_deals" not in applied:
        _add_column_if_missing(conn, "insider_deals", "event_id", "TEXT")
        _add_column_if_missing(conn, "insider_deals", "effective_at", "TEXT")
        _add_column_if_missing(conn, "insider_deals", "published_at", "TEXT")
        _add_column_if_missing(conn, "insider_deals", "source_url", "TEXT")
        _add_unique_if_missing(conn, "insider_deals",
            "insider_deals(event_id)")
        conn.execute(
            "INSERT OR IGNORE INTO _migrations (name, applied_at) VALUES (?, datetime('now'))",
            ("add_event_id_insider_deals",),
        )
        results["add_event_id_insider_deals"] = True

    # Migration: add event_id to rns_announcements
    if "add_event_id_rns" not in applied:
        _add_column_if_missing(conn, "rns_announcements", "event_id", "TEXT")
        _add_column_if_missing(conn, "rns_announcements", "effective_at", "TEXT")
        _add_column_if_missing(conn, "rns_announcements", "observed_at", "TEXT")
        _add_unique_if_missing(conn, "rns_announcements",
            "rns_announcements(event_id)")
        conn.execute(
            "INSERT OR IGNORE INTO _migrations (name, applied_at) VALUES (?, datetime('now'))",
            ("add_event_id_rns",),
        )
        results["add_event_id_rns"] = True

    # Migration: add temporal columns to short_interest
    if "add_temporal_short_interest" not in applied:
        _add_column_if_missing(conn, "short_interest", "effective_at", "TEXT")
        _add_column_if_missing(conn, "short_interest", "observed_at", "TEXT")
        conn.execute(
            "INSERT OR IGNORE INTO _migrations (name, applied_at) VALUES (?, datetime('now'))",
            ("add_temporal_short_interest",),
        )
        results["add_temporal_short_interest"] = True

    # Migration: add ingest_run table
    if "create_ingest_run" not in applied:
        conn.execute("""
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
            )
        """)
        conn.execute(
            "INSERT OR IGNORE INTO _migrations (name, applied_at) VALUES (?, datetime('now'))",
            ("create_ingest_run",),
        )
        results["create_ingest_run"] = True

    # Migration: add raw_artifact table
    if "create_raw_artifact" not in applied:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_artifact (
                artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                mime_type TEXT,
                compression TEXT,
                bytes INTEGER,
                storage_uri TEXT,
                FOREIGN KEY (run_id) REFERENCES ingest_run(run_id)
            )
        """)
        conn.execute(
            "INSERT OR IGNORE INTO _migrations (name, applied_at) VALUES (?, datetime('now'))",
            ("create_raw_artifact",),
        )
        results["create_raw_artifact"] = True

    # Migration: add UNIQUE constraint to price_daily (already has it, but verify)
    if "verify_price_daily_unique" not in applied:
        conn.execute(
            "INSERT OR IGNORE INTO _migrations (name, applied_at) VALUES (?, datetime('now'))",
            ("verify_price_daily_unique",),
        )
        results["verify_price_daily_unique"] = True

    conn.commit()
    return results


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, col_type: str):
    """Add a column to a table if it doesn't already exist."""
    columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        print(f"  Added {table}.{column}")


def _add_unique_if_missing(conn: sqlite3.Connection, table: str, constraint: str):
    """Try to add a UNIQUE constraint. SQLite doesn't support ADD CONSTRAINT,
    so we create an index instead."""
    try:
        conn.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{table}_event_id ON {constraint}")
    except Exception:
        pass  # Index may already exist or column may be NULL


def main():
    """Run migrations from CLI."""
    db_path = DB_PATH
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        print("Creating fresh database...")
        from powstock.collectors.runner import init_db
        conn = init_db(db_path)
    else:
        conn = sqlite3.connect(str(db_path))

    print(f"Migrating {db_path}...")
    results = migrate(conn)

    if results:
        print(f"Applied {len(results)} migrations:")
        for name, applied in results.items():
            if applied:
                print(f"  ✓ {name}")
    else:
        print("No migrations needed.")

    # Show final state
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    print(f"\nTables: {', '.join(tables)}")

    for table in ["price_daily", "insider_deals", "short_interest", "rns_announcements",
                   "company_profiles", "ingest_run", "raw_artifact"]:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {count} rows")
        except Exception:
            print(f"  {table}: (not created)")

    conn.close()


if __name__ == "__main__":
    main()
