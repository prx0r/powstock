"""powstock doctor — auto-status of all data sources.

Run: python -m powstock.doctor

Status: STALE
- Never imported by any module.
- Only reachable via Makefile `make doctor` target.
- Hardcodes Path("data/powstock.db").
- Superseded by layer1/health.py which has 3-level health monitoring.
- To use: make doctor or python -m powstock.doctor.
"""

import sys
from datetime import datetime


def doctor():
    """Print status of all data sources and their pipeline stages."""
    print(f"\nPOWSTOCK Doctor — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print(f"{'SOURCE':<30} {'DISCOVERY':>10} {'RAW':>10} {'PARSE':>10} {'NORMALIZE':>10} {'TEST':>10}")
    print("-" * 80)

    sources = [
        ("Yahoo Finance Prices", "✓", "✓", "✓", "✓", "✗"),
        ("FCA Short Disclosure", "✓", "✓", "✓", "✓", "✗"),
        ("CH Company API", "✓", "~", "✓", "✓", "✗"),
        ("CH PSC Bulk", "✓", "~", "~", "✗", "✗"),
        ("CH PSC API", "✓", "~", "✓", "✓", "✗"),
        ("Investegate RNS", "✓", "✗", "✓", "✓", "✗"),
        ("Investegate PDMR", "✓", "✗", "✓", "✓", "✗"),
        ("FCA TR-1", "✓", "✗", "~", "✗", "✗"),
        ("Takeover Panel", "✓", "✗", "~", "✗", "✗"),
        ("Tracefour PDMR", "✓", "?", "✓", "~", "✗"),
        ("Finnhub Insider", "✓", "?", "✓", "~", "✗"),
        ("iXBRL Financials", "✓", "?", "~", "~", "✗"),
    ]

    for name, disc, raw, parse, norm, test in sources:
        print(f"{name:<30} {disc:>10} {raw:>10} {parse:>10} {norm:>10} {test:>10}")

    print("-" * 80)

    # Check database
    from pathlib import Path
    db_path = Path("data/powstock.db")
    if db_path.exists():
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        print("\nDatabase Status:")
        for table in ["price_daily", "insider_deals", "short_interest",
                       "rns_announcements", "company_profiles", "ingest_run"]:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"  {table:<25} {count:>6} rows")
            except Exception:
                print(f"  {table:<25} (not created)")
        conn.close()
    else:
        print("\nDatabase: not found")

    # Check env
    print("\nEnvironment:")
    from powstock.settings import get_settings
    settings = get_settings()
    ch_key = settings.companies_house_api_key
    print(f"  CH API key: {'configured' if ch_key else 'NOT SET'}")
    print(f"  Database: {settings.database_url}")

    print("\nLegend: ✓=working ~=partial ✗=missing ?=unknown")
    print()


if __name__ == "__main__":
    doctor()
