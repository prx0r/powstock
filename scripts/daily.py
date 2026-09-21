"""Daily cron job for powstock.

Runs all collectors, builds daily state, and exports k3 data.
Designed for crontab or systemd timer.

Usage: python scripts/daily.py [--skip-backfill]
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path("data/powstock.db")


def daily_run(skip_backfill: bool = False) -> dict[str, Any]:
    """Execute the full daily pipeline.

    Layer 1 (collection) runs unconditionally.
    Layer 2 (signals, k3 export) runs only if powk is installed.
    """
    from powstock.collectors.runner import init_db, run_all

    results: dict[str, Any] = {}

    # Step 1: Run all collectors (Layer 1 — always runs)
    print(f"[{datetime.now().isoformat()}] Step 1: Running collectors...")
    conn = init_db(DB_PATH)
    collector_results = run_all(conn)
    results["collectors"] = collector_results

    # Step 2: Backfill prices if needed (Layer 1)
    if not skip_backfill:
        price_count = conn.execute("SELECT COUNT(*) FROM price_daily").fetchone()[0]
        if price_count < 1000:
            print(f"[{datetime.now().isoformat()}] Step 2: Backfilling prices...")
            from scripts.backfill_prices import backfill_prices
            backfill_prices(conn, days=365)
            conn.commit()
        else:
            print(f"[{datetime.now().isoformat()}] Step 2: Prices already backfilled ({price_count} rows)")
    else:
        print(f"[{datetime.now().isoformat()}] Step 2: Skipping backfill")

    # Step 3: Build daily state (Layer 1)
    print(f"[{datetime.now().isoformat()}] Step 3: Building daily state...")
    from scripts.build_daily_state import build_daily_state
    today = datetime.now().date()
    states = build_daily_state(conn, today)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pow_company_state_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            state_json TEXT NOT NULL,
            UNIQUE(date, ticker)
        )
    """)
    import json as _json
    for state in states:
        conn.execute("""
            INSERT OR REPLACE INTO pow_company_state_daily (date, ticker, state_json)
            VALUES (?, ?, ?)
        """, (today.isoformat(), state["ticker"], _json.dumps(state, default=str)))
    conn.commit()
    results["daily_states"] = len(states)

    # Step 4-6: Layer 2 (requires powk — graceful degradation if missing)
    try:
        from layer2.signals import signal_summary
        from layer2.bridge import export_all, print_export_summary

        print(f"[{datetime.now().isoformat()}] Step 4: Computing signals...")
        summary = signal_summary(conn)
        results["signals"] = summary

        print(f"[{datetime.now().isoformat()}] Step 5: Exporting k3...")
        export = export_all(conn)
        print_export_summary(export)
        results["k3_export"] = {k: len(v) for k, v in export.items()}

        k3_dir = Path("data/k3_export")
        k3_dir.mkdir(parents=True, exist_ok=True)
        from dataclasses import asdict
        for kind, objects in export.items():
            path = k3_dir / f"{kind}.jsonl"
            with open(path, "w") as f:
                for obj in objects:
                    f.write(_json.dumps(asdict(obj), sort_keys=True, default=str) + "\n")
        print(f"[{datetime.now().isoformat()}] k3 export saved to {k3_dir}/")
    except ImportError:
        print(f"[{datetime.now().isoformat()}] Steps 4-6: Skipped (powk not installed)")
        results["signals"] = {}
        results["k3_export"] = {}

    conn.close()
    return results


def main():
    skip_backfill = "--skip-backfill" in sys.argv
    results = daily_run(skip_backfill=skip_backfill)

    print(f"\n{'='*60}")
    print("Daily run complete:")
    print(f"  Collectors: {results['collectors']}")
    print(f"  Daily states: {results['daily_states']}")
    print(f"  Signals: {len(results['signals'])} types")
    print(f"  k3 export: {results['k3_export']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
