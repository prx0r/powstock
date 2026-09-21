"""Insider conviction scorer.

Classifies insider transactions by conviction level based on:
- Transaction type (open market purchase = high conviction)
- Value (higher = more conviction)
- Role (CEO buying > NED buying)
- Cluster (multiple insiders buying = stronger signal)
- Streak (consecutive buys = highest conviction)
- Price context (buying after decline = contrarian conviction)
"""

from typing import Any


def score_conviction(
    transaction: dict[str, Any],
    cluster_info: dict[str, Any] | None = None,
    streak_info: dict[str, Any] | None = None,
    price_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score conviction level of an insider transaction.

    Returns:
        {
            "score": float (0-1),
            "level": str (LOW/MEDIUM/HIGH/VERY_HIGH),
            "factors": list[str],
            "conviction_buy": bool,
        }
    """
    factors = []
    score = 0.0

    # 1. Transaction type
    tx_type = transaction.get("transaction_class", "").upper()
    if tx_type == "OPEN_MARKET_PURCHASE":
        score += 0.4
        factors.append("open_market_purchase")
    elif tx_type == "OPTION_EXERCISE":
        score += 0.1
        factors.append("option_exercise")
    elif tx_type == "RSU_VESTING":
        score += 0.05
        factors.append("rsu_vesting")
    elif tx_type == "TAX_SALE":
        score -= 0.2
        factors.append("tax_sale")

    # 2. Value
    value = transaction.get("value", 0) or transaction.get("gross_value", 0) or 0
    if value >= 1000000:  # £1M+
        score += 0.3
        factors.append("very_high_value")
    elif value >= 500000:  # £500k+
        score += 0.25
        factors.append("high_value")
    elif value >= 100000:  # £100k+
        score += 0.2
        factors.append("significant_value")
    elif value >= 50000:  # £50k+
        score += 0.15
        factors.append("moderate_value")
    elif value >= 10000:  # £10k+
        score += 0.1
        factors.append("low_value")

    # 3. Role
    role = (transaction.get("role", "") or transaction.get("reporter", {}).get("officer_title", "")).lower()
    if any(t in role for t in ["ceo", "chief executive", "managing director"]):
        score += 0.25
        factors.append("ceo_buying")
    elif any(t in role for t in ["cfo", "chief financial"]):
        score += 0.2
        factors.append("cfo_buying")
    elif any(t in role for t in ["chair", "chairman"]):
        score += 0.15
        factors.append("chair_buying")
    elif any(t in role for t in ["director", "non-executive"]):
        score += 0.1
        factors.append("director_buying")

    # 4. Cluster (multiple insiders buying)
    if cluster_info:
        count = cluster_info.get("count", 0)
        if count >= 5:
            score += 0.25
            factors.append("strong_cluster")
        elif count >= 3:
            score += 0.2
            factors.append("cluster_buying")
        elif count >= 2:
            score += 0.1
            factors.append("dual_buying")

    # 5. Streak (consecutive buying)
    if streak_info:
        streak_len = streak_info.get("length_weeks", 0)
        if streak_len >= 4:
            score += 0.2
            factors.append("extended_streak")
        elif streak_len >= 2:
            score += 0.1
            factors.append("repeated_buying")

    # 6. Price context
    if price_context:
        drawdown = price_context.get("drawdown_from_high_pct", 0)
        if drawdown < -0.3:  # 30%+ below high
            score += 0.15
            factors.append("deep_value_buy")
        elif drawdown < -0.15:  # 15%+ below high
            score += 0.1
            factors.append("contrarian_buy")

    # Cap at 1.0
    score = min(score, 1.0)

    # Determine level
    if score >= 0.8:
        level = "VERY_HIGH"
    elif score >= 0.6:
        level = "HIGH"
    elif score >= 0.4:
        level = "MEDIUM"
    elif score >= 0.2:
        level = "LOW"
    else:
        level = "VERY_LOW"

    return {
        "score": round(score, 3),
        "level": level,
        "factors": factors,
        "conviction_buy": score >= 0.5,
    }


def score_company_insider_activity(
    transactions: list[dict[str, Any]],
    clusters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Score overall insider activity for a company.

    Returns aggregate conviction metrics.
    """
    if not transactions:
        return {"score": 0, "level": "NONE", "conviction_buy_count": 0}

    buys = [t for t in transactions if t.get("direction") == "P"]
    sells = [t for t in transactions if t.get("direction") == "S"]

    # Score each buy
    scored = [score_conviction(t, clusters) for t in buys]
    conviction_buys = [s for s in scored if s["conviction_buy"]]

    # Aggregate
    buy_value = sum(t.get("value", 0) or t.get("gross_value", 0) or 0 for t in buys)
    sell_value = sum(t.get("value", 0) or t.get("gross_value", 0) or 0 for t in sells)

    # Find matching cluster
    company_cluster = None
    if clusters:
        for c in clusters:
            if c.get("ticker") == transactions[0].get("ticker"):
                company_cluster = c
                break

    # Overall score
    if conviction_buys:
        avg_score = sum(s["score"] for s in conviction_buys) / len(conviction_buys)
    else:
        avg_score = 0.0

    # Adjust for net buying
    if buy_value > sell_value * 2:
        avg_score = min(avg_score + 0.1, 1.0)

    # Adjust for cluster
    if company_cluster and company_cluster.get("count", 0) >= 3:
        avg_score = min(avg_score + 0.15, 1.0)

    if avg_score >= 0.7:
        level = "STRONG_BUY_SIGNAL"
    elif avg_score >= 0.5:
        level = "BUY_SIGNAL"
    elif avg_score >= 0.3:
        level = "MODERATE_SIGNAL"
    else:
        level = "WEAK_SIGNAL"

    return {
        "score": round(avg_score, 3),
        "level": level,
        "total_transactions": len(transactions),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "buy_value": buy_value,
        "sell_value": sell_value,
        "net_value": buy_value - sell_value,
        "conviction_buy_count": len(conviction_buys),
        "conviction_buys": conviction_buys[:5],  # top 5
    }
