"""Wire up powuk physical constraint data.

Connects powuk's existing collectors to powstock's daily state.
powuk already collects: grid demand, generation mix, solar, DNO flexibility,
planning applications, procurement, company capacity, apprenticeships, labour.
"""

from datetime import date
from typing import Any


def fetch_powuk_constraint_data() -> dict[str, Any]:
    """Fetch physical constraint data from powuk.

    Returns data that can be joined to pow_company_state_daily.
    """
    import sys
    sys.path.insert(0, "/root/powuk")

    try:
        import sqlite3
        conn = sqlite3.connect("/root/powuk/data/powuk.db")
        conn.row_factory = sqlite3.Row

        # Get latest observations
        cursor = conn.execute("""
            SELECT source, metric, value, unit, event_time
            FROM observation
            WHERE event_time >= date('now', '-7 days')
            ORDER BY event_time DESC
        """)

        observations = {}
        for row in cursor.fetchall():
            source = row["source"]
            metric = row["metric"]
            key = f"{source}.{metric}"
            if key not in observations:
                observations[key] = {
                    "source": source,
                    "metric": metric,
                    "value": row["value"],
                    "unit": row["unit"],
                    "event_time": row["event_time"],
                }

        conn.close()
        return observations

    except Exception as e:
        print(f"Error fetching powuk data: {e}")
        return {}


def get_constraint_scores() -> dict[str, dict[str, float]]:
    """Get constraint scores for powstock universe companies.

    Maps powuk physical constraints to powstock company bottleneck tags.
    """
    observations = fetch_powuk_constraint_data()

    # Map powuk metrics to powstock constraint scores
    scores = {}

    # Grid constraints -> grid-related companies
    grid_keys = [k for k in observations if "grid" in k.lower() or "demand" in k.lower()]
    if grid_keys:
        latest = observations[grid_keys[0]]
        try:
            value = float(latest["value"])
            # Normalise to 0-1 score
            score = min(value / 50000, 1.0)  # 50GW = max score
        except (ValueError, TypeError):
            score = 0.0

        scores["grid"] = {
            "constraint_score": score,
            "demand_score": score,
        }

    # Solar/generation -> energy companies
    solar_keys = [k for k in observations if "solar" in k.lower() or "generation" in k.lower()]
    if solar_keys:
        scores["energy"] = {
            "constraint_score": 0.5,  # placeholder
            "demand_score": 0.5,
        }

    # Planning applications -> construction/infrastructure
    planning_keys = [k for k in observations if "planning" in k.lower()]
    if planning_keys:
        scores["infrastructure"] = {
            "constraint_score": 0.3,
            "demand_score": 0.4,
        }

    # Labour/apprenticeships -> labour scarcity
    labour_keys = [k for k in observations if "labour" in k.lower() or "apprentice" in k.lower()]
    if labour_keys:
        scores["labour"] = {
            "constraint_score": 0.6,
            "demand_score": 0.5,
        }

    return scores


def enrich_daily_state(
    state: dict[str, Any],
    constraint_scores: dict[str, dict[str, float]],
) -> dict[str, Any]:
    """Enrich a daily state record with powuk constraint data."""
    pow_domains = state.get("pow_domains", [])

    # Match company's POW domains to constraint scores
    for domain in pow_domains:
        domain_lower = domain.lower()
        if "grid" in domain_lower or "power" in domain_lower:
            if "grid" in constraint_scores:
                state["constraint_score"] = constraint_scores["grid"]["constraint_score"]
                state["demand_score"] = constraint_scores["grid"]["demand_score"]
        elif "energy" in domain_lower:
            if "energy" in constraint_scores:
                state["constraint_score"] = constraint_scores["energy"]["constraint_score"]
                state["demand_score"] = constraint_scores["energy"]["demand_score"]
        elif "labour" in domain_lower:
            if "labour" in constraint_scores:
                state["labour_scarcity_score"] = constraint_scores["labour"]["constraint_score"]

    return state
