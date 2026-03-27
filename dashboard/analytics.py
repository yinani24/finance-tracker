"""Analytics data layer that computes all KPIs, trends, and scores for the dashboard."""
from __future__ import annotations
import pandas as pd
from datetime import date
from core.cards import (
    compute_optimal_card_per_category,
    compute_card_annual_value,
    compute_missed_rewards,
    compute_upgrade_recommendations,
)


def compute_card_intelligence(
    df: pd.DataFrame, cards: dict | None, today: date | None = None
) -> dict:
    """Compute credit card optimization intelligence from transaction history.

    Args:
        df: Full transactions DataFrame.
        cards: Cards config dict with a "cards" list, or None.
        today: Reference date for the trailing 3-month window; defaults to today's date.

    Returns:
        Dict with has_cards, optimal_per_category, card_values,
        missed_rewards_annual, upgrade_recommendations.
    """
    _empty: dict = {
        "has_cards": False,
        "optimal_per_category": [],
        "card_values": [],
        "missed_rewards_annual": 0.0,
        "upgrade_recommendations": [],
    }
    card_list = (cards or {}).get("cards", [])
    if not card_list or df.empty:
        return _empty

    if today is None:
        today = date.today()

    # Annualised spending by category from the last 3 months
    expense_df = df[df["amount"] < 0].copy()
    expense_df["month"] = expense_df["date"].dt.strftime("%Y-%m")
    month_list = []
    for i in range(2, -1, -1):
        yr = today.year + (today.month - 1 - i) // 12
        mo = ((today.month - 1 - i) % 12) + 1
        month_list.append(f"{yr:04d}-{mo:02d}")

    spending_by_category: dict[str, float] = {}
    for cat in expense_df["category"].unique():
        cat_df = expense_df[expense_df["category"] == cat]
        total_3mo = float(abs(cat_df[cat_df["month"].isin(month_list)]["amount"].sum()))
        spending_by_category[cat] = round(total_3mo / 3 * 12, 2)

    return {
        "has_cards": True,
        "optimal_per_category": compute_optimal_card_per_category(card_list, spending_by_category),
        "card_values": [compute_card_annual_value(c, spending_by_category) for c in card_list],
        "missed_rewards_annual": compute_missed_rewards(spending_by_category, card_list),
        "upgrade_recommendations": compute_upgrade_recommendations(spending_by_category, card_list),
    }


def build_context(
    df: pd.DataFrame, accounts: dict, goals: dict,
    cards: dict | None = None, today: date | None = None
) -> dict:
    """Assemble the full template context dictionary from raw data inputs.

    Args:
        df: DataFrame of all transactions with at least date, amount, category, and merchant columns.
        accounts: Accounts config dict with an "accounts" list of account objects.
        goals: Goals config dict with "monthly_target", "goals", and "monthly_streak" keys.
        cards: Cards config dict with a "cards" list, or None.
        today: Reference date used for month calculations; defaults to today's date.

    Returns:
        A dict containing kpis, category_trends, health, cuts, action_plan, spending_pct,
        account_balances, top_merchants, trend_labels, trend_values, goals_display,
        monthly_streak, monthly_target, card_intel, and generated_at.
    """
    if today is None:
        today = date.today()
    this_month = today.strftime("%Y-%m")

    kpis             = compute_kpis(df, accounts, goals, today=today)
    category_trends  = compute_category_trends(df, months=3, today=today)
    health           = compute_health_score(kpis, category_trends, goals)
    cuts             = compute_actionable_cuts(df, category_trends)
    action_plan      = compute_action_plan(cuts, goals, kpis, today=today)
    spending_pct     = compute_spending_pct_of_income(df, kpis["income"], today=today)
    account_balances = compute_account_balances(accounts)
    top_merchants    = compute_top_merchants(df, this_month)
    card_intel       = compute_card_intelligence(df, cards, today=today)

    # 12-month spending trend
    trend_labels, trend_values = [], []
    for i in range(11, -1, -1):
        yr = today.year + (today.month - 1 - i) // 12
        mo = ((today.month - 1 - i) % 12) + 1
        label = f"{yr:04d}-{mo:02d}"
        trend_labels.append(label)
        if not df.empty:
            m_df = df[(df["date"].dt.strftime("%Y-%m") == label) & (df["amount"] < 0)]
            trend_values.append(round(float(abs(m_df["amount"].sum())), 2))
        else:
            trend_values.append(0.0)

    # Goals display for Goals tab
    goals_display = []
    for g in goals.get("goals", []):
        pct = int(g["current_amount"] / g["target_amount"] * 100) if g["target_amount"] > 0 else 0
        goals_display.append({
            "name":     g["name"],
            "pct":      pct,
            "current":  g["current_amount"],
            "target":   g["target_amount"],
            "deadline": g["deadline"],
            "created":  g.get("created", ""),
        })

    return {
        "kpis":             kpis,
        "category_trends":  category_trends,
        "health":           health,
        "cuts":             cuts,
        "action_plan":      action_plan,
        "spending_pct":     spending_pct,
        "account_balances": account_balances,
        "top_merchants":    top_merchants,
        "trend_labels":     trend_labels,
        "trend_values":     trend_values,
        "goals_display":    goals_display,
        "monthly_streak":   goals.get("monthly_streak", {}),
        "monthly_target":   goals.get("monthly_target", 0.0),
        "card_intel":       card_intel,
        "generated_at":     today.strftime("%Y-%m-%d"),
    }


def compute_kpis(df: pd.DataFrame, accounts: dict, goals: dict, today: date | None = None) -> dict:
    """Compute current-month KPIs including net worth, income, expenses, and savings rate.

    Args:
        df: Full transactions DataFrame.
        accounts: Accounts config dict with an "accounts" list.
        goals: Goals config dict providing the monthly savings target.
        today: Reference date for determining the current month; defaults to today's date.

    Returns:
        A dict with net_worth, income, expenses, saved, monthly_target, savings_rate, and this_month.
    """
    if today is None:
        today = date.today()
    this_month = today.strftime("%Y-%m")

    net_worth = sum(a["balance"] for a in accounts.get("accounts", []))

    if df.empty:
        return {
            "net_worth": net_worth, "income": 0.0, "expenses": 0.0,
            "saved": 0.0, "monthly_target": goals.get("monthly_target", 0.0),
            "savings_rate": 0.0, "this_month": this_month,
        }

    month_df = df[df["date"].dt.strftime("%Y-%m") == this_month]
    income   = float(month_df[month_df["amount"] > 0]["amount"].sum())
    expenses = float(abs(month_df[month_df["amount"] < 0]["amount"].sum()))
    saved    = income - expenses

    return {
        "net_worth":      net_worth,
        "income":         round(income, 2),
        "expenses":       round(expenses, 2),
        "saved":          round(saved, 2),
        "monthly_target": goals.get("monthly_target", 0.0),
        "savings_rate":   (saved / income) if income > 0 else 0.0,
        "this_month":     this_month,
    }


def compute_category_trends(df: pd.DataFrame, months: int = 3, today: date | None = None) -> list:
    """Compute per-category spending amounts and month-over-month trend direction.

    Args:
        df: Full transactions DataFrame.
        months: Number of trailing months to include in the trend window.
        today: Reference date for the current month; defaults to today's date.

    Returns:
        A list of dicts, each with name, current_amount, prior_amounts, pct_change, and direction.
        Returns an empty list when df is empty.
    """
    if today is None:
        today = date.today()
    if df.empty:
        return []

    expense_df = df[df["amount"] < 0].copy()
    expense_df["month"] = expense_df["date"].dt.strftime("%Y-%m")

    # Build month list oldest→current, length=months
    month_list = []
    for i in range(months - 1, -1, -1):
        yr = today.year + (today.month - 1 - i) // 12
        mo = ((today.month - 1 - i) % 12) + 1
        month_list.append(f"{yr:04d}-{mo:02d}")

    categories = sorted(expense_df["category"].unique())
    result = []
    for cat in categories:
        cat_df = expense_df[expense_df["category"] == cat]
        amounts = []
        for m in month_list:
            amt = float(abs(cat_df[cat_df["month"] == m]["amount"].sum()))
            amounts.append(round(amt, 2))

        current = amounts[-1]
        prior   = amounts[-2] if len(amounts) >= 2 else 0.0
        pct_change = round((current - prior) / prior, 4) if prior > 0 else 0.0

        if pct_change > 0.05:
            direction = "up"
        elif pct_change < -0.05:
            direction = "down"
        else:
            direction = "flat"

        result.append({
            "name":          cat,
            "current_amount": current,
            "prior_amounts":  amounts[:-1],
            "pct_change":     pct_change,
            "direction":      direction,
        })
    return result


def compute_health_score(kpis: dict, category_trends: list, goals: dict, today: date | None = None) -> dict:
    """Compute a 0–100 financial health score across five weighted dimensions.

    Args:
        kpis: KPI dict as returned by compute_kpis.
        category_trends: Category trend list as returned by compute_category_trends.
        goals: Goals config dict.
        today: Reference date for goal at-risk calculations; defaults to today's date.

    Returns:
        A dict with score (int), grade (str), passing (list[str]), and failing (list[str]).
    """
    score   = 0.0
    passing = []
    failing = []

    # 1. Savings rate (30 pts, linear)
    savings_pts = min(kpis["savings_rate"] / 0.20, 1.0) * 30
    score += savings_pts
    if savings_pts >= 25:
        passing.append("Savings rate")
    else:
        failing.append("Savings rate")

    # 2. Spending trend (25 pts, -8 per category up >20% MoM)
    offending = [t for t in category_trends if t["pct_change"] > 0.20]
    trend_pts = max(0.0, 25.0 - len(offending) * 8)
    score += trend_pts
    for t in offending:
        failing.append(f"{t['name']} spending")
    if not offending:
        passing.append("Spending trends")

    # 3. Goal progress (25 pts, -12 per at-risk goal)
    at_risk   = _get_at_risk_goals(goals, today=today)
    goal_pts  = max(0.0, 25.0 - len(at_risk) * 12)
    score    += goal_pts
    for g in at_risk:
        failing.append(f"{g['name']} goal")
    if not at_risk:
        passing.append("Goal progress")

    # 4. Subscription ratio (10 pts)
    income     = kpis["income"]
    sub_trend  = next((t for t in category_trends if t["name"] == "Subscriptions"), None)
    sub_amount = sub_trend["current_amount"] if sub_trend else 0.0
    sub_ratio  = sub_amount / income if income > 0 else 0.0
    if sub_ratio < 0.08:
        score += 10
        passing.append("Subscription ratio")
    elif sub_ratio <= 0.15:
        score += 5
    else:
        failing.append("Subscriptions")

    # 5. Emergency fund (10 pts if >50% complete)
    ef = next((g for g in goals.get("goals", []) if "emergency" in g["name"].lower()), None)
    if ef:
        ef_pct = ef["current_amount"] / ef["target_amount"] if ef["target_amount"] > 0 else 0.0
        if ef_pct >= 0.50:
            score += 10
            passing.append("Emergency fund")
        else:
            failing.append("Emergency fund")
    else:
        score += 5  # no emergency fund goal = partial credit

    score = round(min(100.0, score))
    return {"score": score, "grade": _score_to_grade(score), "passing": passing, "failing": failing}


def compute_actionable_cuts(df: pd.DataFrame, category_trends: list) -> list:
    """Identify specific spending categories or merchants where cuts are recommended.

    Args:
        df: Full transactions DataFrame.
        category_trends: Category trend list as returned by compute_category_trends.

    Returns:
        A list of cut suggestion dicts sorted by potential_saving descending, each containing
        category, description, detail, potential_saving, and icon. Returns an empty list when
        df is empty or no trends are available.
    """
    if df.empty or not category_trends:
        return []

    cuts = []
    this_month = df["date"].dt.strftime("%Y-%m").max() if not df.empty else ""

    for trend in category_trends:
        cat = trend["name"]

        # Subscriptions: list individual merchants ≥ $15/mo
        if cat == "Subscriptions":
            sub_df = df[
                (df["category"] == "Subscriptions") &
                (df["amount"] < 0) &
                (df["date"].dt.strftime("%Y-%m") == this_month)
            ]
            if not sub_df.empty:
                by_m = sub_df.groupby("merchant")["amount"].sum().abs().sort_values(ascending=False)
                cuttable = [(m, v) for m, v in by_m.items() if v >= 15.0]
                if cuttable:
                    names_str = ", ".join(f"{m} (${v:.2f})" for m, v in cuttable[:3])
                    total = round(sum(v for _, v in cuttable), 2)
                    cuts.append({
                        "category":        "Subscriptions",
                        "description":     f"Subscriptions: {names_str}",
                        "detail":          f"These recurring charges total ${total:,.2f}/mo",
                        "potential_saving": total,
                        "icon":            "📺",
                    })
            continue

        # General: flag if current > 3-month average × 1.15
        all_amounts = trend["prior_amounts"] + [trend["current_amount"]]
        avg = sum(trend["prior_amounts"]) / len(trend["prior_amounts"]) if trend["prior_amounts"] else 0.0
        if avg > 0 and trend["current_amount"] > avg * 1.15:
            saving = round(trend["current_amount"] - avg, 2)
            pct_str = f"{trend['pct_change'] * 100:.0f}%"
            cuts.append({
                "category":        cat,
                "description":     f"{cat} is up {pct_str} vs 3-month average",
                "detail":          f"You spent ${trend['current_amount']:,.2f} this month vs avg ${avg:,.2f}",
                "potential_saving": saving,
                "icon":            _category_icon(cat),
            })

    # Transport ride-count check
    transport_df = df[df["category"] == "Transport"]
    if not transport_df.empty:
        monthly_counts = transport_df.groupby(transport_df["date"].dt.strftime("%Y-%m")).size()
        avg_rides = monthly_counts.mean()
        if avg_rides > 10:
            this_month_tr = transport_df[transport_df["date"].dt.strftime("%Y-%m") == this_month]
            avg_cost = abs(this_month_tr["amount"].sum()) / max(1, len(this_month_tr))
            short_trips = max(1, int(avg_rides * 0.20))
            saving = round(short_trips * avg_cost, 2)
            # Only add if not already flagged via the general path
            if not any(c["category"] == "Transport" for c in cuts):
                cuts.append({
                    "category":        "Transport",
                    "description":     f"Averaged {avg_rides:.0f} rides/mo — consider walking short trips",
                    "detail":          f"~{short_trips} short trips/mo at avg ${avg_cost:.2f} each",
                    "potential_saving": saving,
                    "icon":            "🚗",
                })

    cuts.sort(key=lambda x: x["potential_saving"], reverse=True)
    return cuts


def compute_action_plan(cuts: list, goals: dict, kpis: dict, today: date | None = None) -> list:
    """Build a prioritised 3-step action plan from the top spending cuts.

    Args:
        cuts: Cut suggestion list as returned by compute_actionable_cuts.
        goals: Goals config dict used to surface the highest-priority at-risk goal.
        kpis: KPI dict as returned by compute_kpis.
        today: Reference date for month label generation; defaults to today's date.

    Returns:
        A list of up to 3 step dicts, each with step, month_label, action, saving,
        goal_link, and description. Returns an empty list when cuts is empty.
    """
    if today is None:
        today = date.today()
    if not cuts:
        return []

    at_risk       = _get_at_risk_goals(goals, today=today)
    at_risk_name  = at_risk[0]["name"] if at_risk else None
    steps         = []

    for i, cut in enumerate(cuts[:3]):
        mo_offset = i
        yr = today.year + (today.month - 1 + mo_offset) // 12
        mo = ((today.month - 1 + mo_offset) % 12) + 1
        month_label = date(yr, mo, 1).strftime("%B %Y")

        goal_link   = at_risk_name if i == 0 else None
        description = f"By {month_label}, reduce {cut['category']} spending → saves ${cut['potential_saving']:,.2f}/mo"
        if goal_link:
            description += f" → helps close {goal_link} shortfall"

        steps.append({
            "step":        i + 1,
            "month_label": month_label,
            "action":      f"Reduce {cut['category']} spending",
            "saving":      cut["potential_saving"],
            "goal_link":   goal_link,
            "description": description,
        })
    return steps


def compute_spending_pct_of_income(df: pd.DataFrame, income: float, today: date | None = None) -> list:
    """Compute each category's current-month spend as a percentage of income.

    Args:
        df: Full transactions DataFrame.
        income: Current-month income amount (positive float).
        today: Reference date for the current month; defaults to today's date.

    Returns:
        A list of dicts sorted by amount descending, each with name, amount, and pct_of_income.
        Returns an empty list when df is empty, income is zero/negative, or no expenses exist.
    """
    if today is None:
        today = date.today()
    if df.empty or income <= 0:
        return []
    this_month = today.strftime("%Y-%m")
    month_df = df[(df["date"].dt.strftime("%Y-%m") == this_month) & (df["amount"] < 0)]
    if month_df.empty:
        return []
    by_cat = month_df.groupby("category")["amount"].sum().abs().sort_values(ascending=False)
    return [
        {"name": cat, "amount": round(float(amt), 2), "pct_of_income": round(float(amt) / income * 100, 1)}
        for cat, amt in by_cat.items()
    ]


def compute_account_balances(accounts: dict) -> list:
    """Compute each account's balance and its share of total positive balances.

    Args:
        accounts: Accounts config dict with an "accounts" list of account objects.

    Returns:
        A list of dicts with name, balance, type, and share_of_total for every account.
        Returns an empty list when no accounts are present.
    """
    accts = accounts.get("accounts", [])
    if not accts:
        return []
    positive_total = sum(a["balance"] for a in accts if a["balance"] > 0)
    return [
        {
            "name":          a["name"],
            "balance":       a["balance"],
            "type":          a.get("type", "checking"),
            "share_of_total": round(a["balance"] / positive_total, 4) if positive_total > 0 and a["balance"] > 0 else 0.0,
        }
        for a in accts
    ]


def compute_top_merchants(df: pd.DataFrame, month: str) -> list:
    """Return the top 10 merchants by total spend for a given month.

    Args:
        df: Full transactions DataFrame.
        month: Month string in YYYY-MM format to filter transactions.

    Returns:
        A list of up to 10 dicts sorted by amount descending, each with name, amount,
        category, and tx_count. Returns an empty list when df is empty or no expenses exist.
    """
    if df.empty:
        return []
    month_df = df[(df["date"].dt.strftime("%Y-%m") == month) & (df["amount"] < 0)]
    if month_df.empty:
        return []
    grouped = (
        month_df.groupby("merchant")
        .agg(amount=("amount", lambda x: abs(x.sum())), tx_count=("amount", "count"), category=("category", "first"))
        .sort_values("amount", ascending=False)
        .head(10)
    )
    return [
        {"name": m, "amount": round(float(r["amount"]), 2), "category": r["category"], "tx_count": int(r["tx_count"])}
        for m, r in grouped.iterrows()
    ]


def _score_to_grade(score: int) -> str:
    """Convert a numeric health score to a letter grade.

    Args:
        score: Integer health score in the range 0–100.

    Returns:
        A letter grade string: "A", "B+", "B", "C", "D", or "F".
    """
    if score >= 90: return "A"
    if score >= 80: return "B+"
    if score >= 75: return "B"
    if score >= 60: return "C"
    if score >= 45: return "D"
    return "F"


def _get_at_risk_goals(goals: dict, today: date | None = None) -> list:
    """Identify goals that are behind their expected progress trajectory.

    Args:
        goals: Goals config dict with a "goals" list of goal objects.
        today: Reference date for progress calculations; defaults to today's date.

    Returns:
        A list of goal dicts whose actual progress percentage is below the expected
        percentage based on elapsed time since creation.
    """
    if today is None:
        today = date.today()
    at_risk = []
    for g in goals.get("goals", []):
        try:
            deadline = date.fromisoformat(g["deadline"] + "-01")
            created  = date.fromisoformat(g["created"])
            total_months   = max(1, (deadline.year - created.year) * 12 + (deadline.month - created.month))
            elapsed_months = max(0, (today.year - created.year) * 12 + (today.month - created.month))
            expected_pct = elapsed_months / total_months
            actual_pct   = g["current_amount"] / g["target_amount"] if g["target_amount"] > 0 else 0.0
            if actual_pct < expected_pct:
                at_risk.append(g)
        except (KeyError, ValueError):
            pass
    return at_risk


def _category_icon(category: str) -> str:
    """Return an emoji icon for a spending category.

    Args:
        category: Category name string.

    Returns:
        An emoji string for known categories, or "💸" as the default fallback.
    """
    return {
        "Food & Dining": "🍔",
        "Transport":     "🚗",
        "Shopping":      "🛍️",
        "Health":        "💊",
        "Entertainment": "🎬",
        "Subscriptions": "📺",
    }.get(category, "💸")
