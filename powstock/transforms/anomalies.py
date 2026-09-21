"""Anomaly detection — adapted from companieshouse.watch.

Four detectors scoring 0-100:
1. Address Cluster — many companies at one address
2. Director Velocity — one person across many companies
3. Officer Churn — company cycling directors
4. Bulk Registration — same-day mass incorporations
"""

from typing import Any


def score_address_cluster(
    company_count: int,
    recently_incorporated: int,
    shared_directors: int,
    is_known_agent: bool = False,
) -> dict[str, Any]:
    """Score address cluster anomaly.

    Formula: LEAST(100, company_count*2 + recent_90d*4 + shared_directors*8)
    """
    score = min(100,
        company_count * 2
        + recently_incorporated * 4
        + shared_directors * 8
    )

    # Cap known formation agents
    if is_known_agent:
        score = min(score, 20)

    return {
        "detector": "address_cluster",
        "score": score,
        "features": {
            "company_count": company_count,
            "recently_incorporated": recently_incorporated,
            "shared_directors": shared_directors,
        },
        "is_known_agent": is_known_agent,
    }


def score_director_velocity(
    total_active: int,
    recent_90d: int,
    recent_30d: int,
) -> dict[str, Any]:
    """Score director velocity anomaly.

    Formula: LEAST(100, total*5 + recent_90d*5 + recent_30d*10)
    """
    score = min(100,
        total_active * 5
        + recent_90d * 5
        + recent_30d * 10
    )

    return {
        "detector": "director_velocity",
        "score": score,
        "features": {
            "total_active": total_active,
            "recent_90d": recent_90d,
            "recent_30d": recent_30d,
        },
    }


def score_officer_churn(
    churn_events_90d: int,
    terminations_90d: int,
) -> dict[str, Any]:
    """Score officer churn anomaly.

    Formula: LEAST(100, churn*8 + terminations*5)
    """
    score = min(100,
        churn_events_90d * 8
        + terminations_90d * 5
    )

    return {
        "detector": "officer_churn",
        "score": score,
        "features": {
            "churn_events_90d": churn_events_90d,
            "terminations_90d": terminations_90d,
        },
    }


def score_bulk_registration(
    companies_on_day: int,
    days_since: int,
) -> dict[str, Any]:
    """Score bulk registration anomaly.

    Formula: LEAST(100, count*5 + recency_bonus(25/10/0))
    """
    if days_since <= 30:
        recency_bonus = 25
    elif days_since <= 90:
        recency_bonus = 10
    else:
        recency_bonus = 0

    score = min(100,
        companies_on_day * 5
        + recency_bonus
    )

    return {
        "detector": "bulk_registration",
        "score": score,
        "features": {
            "companies_on_day": companies_on_day,
            "days_since": days_since,
            "recency_bonus": recency_bonus,
        },
    }


def detect_anomalies(
    company_data: dict[str, Any],
    director_data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Run all anomaly detectors on a company.

    Returns list of anomaly dicts with detector, score, features.
    """
    anomalies = []

    # Address cluster
    if company_data.get("address_company_count", 0) >= 5:
        result = score_address_cluster(
            company_count=company_data.get("address_company_count", 0),
            recently_incorporated=company_data.get("address_recent_90d", 0),
            shared_directors=company_data.get("address_shared_directors", 0),
            is_known_agent=company_data.get("is_known_agent", False),
        )
        if result["score"] >= 20:
            anomalies.append(result)

    # Director velocity
    if director_data:
        total = director_data.get("total_active", 0)
        if total >= 3:
            result = score_director_velocity(
                total_active=total,
                recent_90d=director_data.get("recent_90d", 0),
                recent_30d=director_data.get("recent_30d", 0),
            )
            if result["score"] >= 30:
                anomalies.append(result)

    # Officer churn
    churn = company_data.get("churn_events_90d", 0)
    if churn >= 5:
        result = score_officer_churn(
            churn_events_90d=churn,
            terminations_90d=company_data.get("terminations_90d", 0),
        )
        if result["score"] >= 30:
            anomalies.append(result)

    # Bulk registration
    bulk = company_data.get("bulk_same_day", 0)
    if bulk >= 10:
        result = score_bulk_registration(
            companies_on_day=bulk,
            days_since=company_data.get("bulk_days_since", 180),
        )
        if result["score"] >= 30:
            anomalies.append(result)

    return anomalies
