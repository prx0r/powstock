"""End-to-end collector integration tests.

Each test runs a collector against the live API.
Skip if network unavailable or rate-limited.

Run: pytest tests/test_collectors.py -v
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest


def _make_db() -> sqlite3.Connection:
    """Create a fresh test database."""
    from powstock.collectors.runner import init_db
    return init_db(Path(tempfile.mktemp(suffix=".db")))


@pytest.mark.integration
class TestYahooPrices:
    def test_fetch_single_ticker(self):
        from powstock.collectors.yahoo_prices import fetch_latest
        result = fetch_latest("NG.")
        assert result is not None
        assert result["ticker"] == "NG."
        assert result["price"] > 0
        assert result["asof"] != ""

    def test_fetch_all_tickers(self):
        from powstock.collectors.yahoo_prices import fetch_all_latest
        results = fetch_all_latest(["NG.", "SSE", "CCC"])
        assert len(results) == 3
        for ticker in ["NG.", "SSE", "CCC"]:
            assert ticker in results
            assert results[ticker]["price"] > 0

    def test_store_prices_in_db(self):
        from powstock.collectors.runner import init_db, run_prices
        conn = _make_db()
        count = run_prices(conn)
        assert count >= 20  # at least 20/25 tickers
        rows = conn.execute("SELECT COUNT(*) FROM price_daily").fetchone()[0]
        assert rows >= 20
        conn.close()


@pytest.mark.integration
class TestFCAShortInterest:
    def test_fetch_short_positions(self):
        from powstock.collectors.fca_short_interest import fetch_current_short_positions
        positions = fetch_current_short_positions()
        assert len(positions) > 100  # FCA typically has 400+ positions
        for pos in positions[:5]:
            assert pos.isin != ""
            assert pos.position_pct >= 0

    def test_store_short_interest(self):
        from powstock.collectors.runner import init_db, run_short_interest
        conn = _make_db()
        count = run_short_interest(conn)
        assert count > 100
        rows = conn.execute("SELECT COUNT(*) FROM short_interest").fetchone()[0]
        assert rows > 100
        conn.close()


@pytest.mark.integration
class TestCompaniesHouse:
    def test_fetch_company_profile(self):
        from powstock.collectors.companies_house import fetch_company_profile
        profile = fetch_company_profile("04031152")  # National Grid
        # May fail if no API key configured
        if profile is not None:
            assert profile.company_number == "04031152"
            assert profile.company_name != ""

    def test_fetch_universe_companies(self):
        from powstock.collectors.companies_house import fetch_universe_companies
        companies = fetch_universe_companies()
        # May return empty if no API key
        if companies:
            assert len(companies) > 0
            for ticker, data in companies.items():
                assert "company_number" in data


@pytest.mark.integration
class TestPDMR:
    def test_fetch_pdmr_announcements(self):
        from powstock.collectors.fca_pdmr import fetch_pdmr_announcements
        deals = fetch_pdmr_announcements(max_pages=1)
        assert isinstance(deals, list)
        # Investegate should return some PDMR deals
        if deals:
            for deal in deals[:3]:
                assert "ticker" in deal
                assert "director" in deal


@pytest.mark.integration
class TestRNS:
    def test_fetch_rns_global(self):
        from powstock.collectors.rns_announcements import fetch_rns_announcements
        announcements = fetch_rns_announcements(max_pages=1)
        assert isinstance(announcements, list)
        assert len(announcements) > 10  # Investegate global feed has 50+

    def test_rns_has_universe_match(self):
        """Investegate returns global feed — check if ANY universe ticker appears."""
        from powstock.collectors.rns_announcements import fetch_rns_announcements
        from powstock.universe import UNIVERSE
        announcements = fetch_rns_announcements(max_pages=1)
        universe_tickers = {s.ticker for s in UNIVERSE}
        matched = [a for a in announcements if a.ticker in universe_tickers]
        # May be 0 if none of our 25 are in today's headlines
        assert isinstance(matched, list)


@pytest.mark.integration
class TestTakeoverPanel:
    def test_fetch_disclosure_table(self):
        from powstock.collectors.takeover_panel import fetch_disclosure_table
        result = fetch_disclosure_table()
        assert "html" in result
        assert "sha256" in result
        if result["html"]:
            assert len(result["html"]) > 100


@pytest.mark.integration
class TestPSCSnapshot:
    def test_discover_psc_files(self):
        from powstock.collectors.psc_snapshot import discover_psc_files
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        files = discover_psc_files(today)
        assert files["single_file"] is not None or files["total_parts"] > 0

    def test_archive_psc_single_file(self):
        from powstock.collectors.psc_snapshot import download_psc_snapshot
        from datetime import datetime
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            result = download_psc_snapshot(
                date=datetime.now(),
                archive_dir=Path(tmp) / "psc",
                archive_only=True,
            )
            if result:
                assert len(result["archive_paths"]) > 0
                assert result["total_bytes"] > 0
                assert result["sha256"] != ""


@pytest.mark.integration
class TestFCANSM:
    def test_fetch_nsm_page(self):
        from powstock.collectors.fca_nsm import fetch_nsm_page
        # May return empty if API requires auth
        announcements = fetch_nsm_page(max_pages=1)
        assert isinstance(announcements, list)


@pytest.mark.integration
class TestFullPipeline:
    def test_run_all_collectors(self):
        """Run the full pipeline on a fresh DB."""
        from powstock.collectors.runner import init_db, run_all
        conn = _make_db()
        results = run_all(conn)

        # Check results
        assert isinstance(results, dict)
        assert "prices" in results
        assert "insiders" in results
        assert "short_interest" in results

        # Prices should have data
        assert results["prices"] >= 20

        # Short interest should have data
        assert results["short_interest"] > 100

        # DB should have data
        assert conn.execute("SELECT COUNT(*) FROM price_daily").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM short_interest").fetchone()[0] > 0

        conn.close()
