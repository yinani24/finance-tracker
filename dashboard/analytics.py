"""Analytics data layer that computes all KPIs, trends, and scores for the dashboard."""
from __future__ import annotations
import pandas as pd
from datetime import date
from core.cards import (
    compute_optimal_card_per_category,
    compute_card_annual_value,
    compute_missed_rewards,
    compute_upgrade_recommendations,
    compute_card_value_per_category,
)


def compute_mom_changes(df: pd.DataFrame, today: date | None = None) -> dict:
    """Compute month-over-month percentage changes for income, expenses, and savings.

    Args:
        df: Full transactions DataFrame.
        today: Reference date for the current month; defaults to today's date.

    Returns:
        A dict with income_change_pct, expenses_change_pct, saved_change_pct.
        Each value is a rounded float or None if prior month has no data.
    """
    if today is None:
        today = date.today()

    this_month = today.strftime("%Y-%m")
    yr = today.year + (today.month - 2) // 12
    mo = ((today.month - 2) % 12) + 1
    prior_month = f"{yr:04d}-{mo:02d}"

    result = {"income_change_pct": None, "expenses_change_pct": None, "saved_change_pct": None}
    if df.empty:
        return result

    cur_df = df[df["date"].dt.strftime("%Y-%m") == this_month]
    prev_df = df[df["date"].dt.strftime("%Y-%m") == prior_month]

    if prev_df.empty:
        return result

    cur_income = float(cur_df[cur_df["amount"] > 0]["amount"].sum())
    cur_expenses = float(abs(cur_df[cur_df["amount"] < 0]["amount"].sum()))
    cur_saved = cur_income - cur_expenses

    prev_income = float(prev_df[prev_df["amount"] > 0]["amount"].sum())
    prev_expenses = float(abs(prev_df[prev_df["amount"] < 0]["amount"].sum()))
    prev_saved = prev_income - prev_expenses

    def _pct(cur: float, prev: float) -> float | None:
        if prev == 0:
            return None
        return round((cur - prev) / abs(prev) * 100, 1)

    result["income_change_pct"] = _pct(cur_income, prev_income)
    result["expenses_change_pct"] = _pct(cur_expenses, prev_expenses)
    result["saved_change_pct"] = _pct(cur_saved, prev_saved)
    return result


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


def compute_subscription_breakdown(df: pd.DataFrame, today: date | None = None) -> dict:
    """Return all recurring subscription services with per-service cost and redundancy flags.

    Args:
        df: Full transactions DataFrame.
        today: Reference date for the trailing 3-month window; defaults to today's date.

    Returns:
        Dict with services (list), total_monthly, total_annual, and redundancy_waste.
    """
    if today is None:
        today = date.today()
    month_list = []
    for i in range(2, -1, -1):
        yr = today.year + (today.month - 1 - i) // 12
        mo = ((today.month - 1 - i) % 12) + 1
        month_list.append(f"{yr:04d}-{mo:02d}")
    empty = {"services": [], "total_monthly": 0.0, "total_annual": 0.0, "redundancy_waste": 0.0}
    if df.empty:
        return empty
    sub_df = df[(df["category"] == "Subscriptions") & (df["amount"] < 0)].copy()
    sub_df["month"] = sub_df["date"].dt.strftime("%Y-%m")
    sub_df = sub_df[sub_df["month"].isin(month_list)]
    if sub_df.empty:
        return empty
    months_present = sub_df.groupby("merchant")["month"].nunique()
    grouped = sub_df.groupby("merchant")["amount"].sum()
    services = []
    for merchant, total in grouped.items():
        n = months_present[merchant]
        monthly = round(abs(total) / n, 2)
        services.append({"name": merchant, "monthly": monthly, "annual": round(monthly * 12, 2), "redundant": False})
    PHONE_KW = ["t-mobile", "tmobile", "visible", "verizon", "straight talk"]
    phone_svcs = [s for s in services if any(kw in s["name"].lower() for kw in PHONE_KW)]
    redundancy_waste = 0.0
    if len(phone_svcs) >= 2:
        for s in phone_svcs:
            s["redundant"] = True
        phone_costs = sorted([s["monthly"] for s in phone_svcs], reverse=True)
        redundancy_waste = round(sum(phone_costs[1:]), 2)
    services.sort(key=lambda x: x["monthly"], reverse=True)
    total_monthly = round(sum(s["monthly"] for s in services), 2)
    return {"services": services, "total_monthly": total_monthly, "total_annual": round(total_monthly * 12, 2), "redundancy_waste": redundancy_waste}


def compute_food_breakdown(df: pd.DataFrame, today: date | None = None) -> list:
    """Return Food & Dining transactions broken down by merchant for the trailing 3 months.

    Args:
        df: Full transactions DataFrame.
        today: Reference date for the trailing 3-month window; defaults to today's date.

    Returns:
        A list of dicts (name, total, visits, avg_ticket) sorted by total descending, top 15.
    """
    if today is None:
        today = date.today()
    month_list = []
    for i in range(2, -1, -1):
        yr = today.year + (today.month - 1 - i) // 12
        mo = ((today.month - 1 - i) % 12) + 1
        month_list.append(f"{yr:04d}-{mo:02d}")
    if df.empty:
        return []
    food_df = df[(df["category"] == "Food & Dining") & (df["amount"] < 0)].copy()
    food_df["month"] = food_df["date"].dt.strftime("%Y-%m")
    food_df = food_df[food_df["month"].isin(month_list)]
    if food_df.empty:
        return []
    grouped = (
        food_df.groupby("merchant")
        .agg(total=("amount", lambda x: round(abs(x.sum()), 2)), visits=("amount", "count"))
        .reset_index()
    )
    grouped["avg_ticket"] = (grouped["total"] / grouped["visits"]).round(2)
    grouped = grouped.sort_values("total", ascending=False).head(15)
    return [
        {"name": r["merchant"], "total": r["total"], "visits": int(r["visits"]), "avg_ticket": r["avg_ticket"]}
        for _, r in grouped.iterrows()
    ]


def compute_fixed_costs(df: pd.DataFrame, accounts: dict, today: date | None = None) -> dict:
    """Identify fixed monthly obligations and their ratio to 3-month average income.

    Args:
        df: Full transactions DataFrame.
        accounts: Accounts config dict (not used directly, reserved for future use).
        today: Reference date for the trailing 3-month window; defaults to today's date.

    Returns:
        Dict with rent, phone, insurance, subscriptions, total, avg_income, pct_of_income.
    """
    if today is None:
        today = date.today()
    month_list = []
    for i in range(2, -1, -1):
        yr = today.year + (today.month - 1 - i) // 12
        mo = ((today.month - 1 - i) % 12) + 1
        month_list.append(f"{yr:04d}-{mo:02d}")
    n = len(month_list)

    def _avg(cat):
        if df.empty:
            return 0.0
        c = df[(df["category"] == cat) & (df["amount"] < 0)].copy()
        c["month"] = c["date"].dt.strftime("%Y-%m")
        return round(abs(c[c["month"].isin(month_list)]["amount"].sum()) / n, 2)

    rent = _avg("Housing")
    phone = _avg("Phone & Cell")
    insurance = _avg("Insurance")
    sub = compute_subscription_breakdown(df, today=today)["total_monthly"]
    total = round(rent + phone + insurance + sub, 2)
    if df.empty:
        avg_income = 0.0
    else:
        inc = df[df["amount"] > 0].copy()
        inc["month"] = inc["date"].dt.strftime("%Y-%m")
        avg_income = round(inc[inc["month"].isin(month_list)]["amount"].sum() / n, 2)
    pct = round(total / avg_income, 4) if avg_income > 0 else 0.0
    return {"rent": rent, "phone": phone, "insurance": insurance, "subscriptions": sub, "total": total, "avg_income": avg_income, "pct_of_income": pct}


def compute_lifestyle_insights(df: pd.DataFrame, kpis: dict, fixed_costs: dict, sub_breakdown: dict, today: date | None = None) -> list:
    """Generate 3–5 personalized, actionable insight strings based on spending data.

    Args:
        df: Full transactions DataFrame.
        kpis: KPI dict as returned by compute_kpis.
        fixed_costs: Fixed costs dict as returned by compute_fixed_costs.
        sub_breakdown: Subscription breakdown dict as returned by compute_subscription_breakdown.
        today: Reference date for the trailing 3-month window; defaults to today's date.

    Returns:
        A list of up to 5 insight strings; always returns at least 1.
    """
    if today is None:
        today = date.today()
    month_list = []
    for i in range(2, -1, -1):
        yr = today.year + (today.month - 1 - i) // 12
        mo = ((today.month - 1 - i) % 12) + 1
        month_list.append(f"{yr:04d}-{mo:02d}")
    insights = []
    phone_waste = sub_breakdown.get("redundancy_waste", 0.0)
    if phone_waste > 0:
        insights.append(f"You have multiple active phone plans — cancelling the cheapest saves ~${phone_waste * 12:.0f}/yr")
    avg_income = fixed_costs.get("avg_income", 0.0)
    rent = fixed_costs.get("rent", 0.0)
    if avg_income > 0 and rent > 0:
        rent_pct = rent / avg_income
        if rent_pct > 0.33:
            target = avg_income * 0.30
            insights.append(f"Rent is {rent_pct*100:.0f}% of avg income — the 30% rule suggests ${target:,.0f}/mo")
    if not df.empty:
        dubai = df[(df["category"] == "Dubai") & (df["amount"] < 0)].copy()
        dubai["month"] = dubai["date"].dt.strftime("%Y-%m")
        dubai_avg = abs(dubai[dubai["month"].isin(month_list)]["amount"].sum()) / 3
        if dubai_avg > 300:
            insights.append(f"International spending averages ${dubai_avg:.0f}/mo — CSP has no FX fee, saving ~${dubai_avg * 0.03 * 12:.0f}/yr vs 3% foreign fee cards")
        food = df[(df["category"] == "Food & Dining") & (df["amount"] < 0)].copy()
        food["month"] = food["date"].dt.strftime("%Y-%m")
        food_avg = abs(food[food["month"].isin(month_list)]["amount"].sum()) / 3
        if food_avg > 500:
            insights.append(f"Dining out costs ${food_avg:.0f}/mo — cooking at home 2 extra nights/week could save ~${food_avg * 0.20:.0f}/mo")
    total_subs = sub_breakdown.get("total_monthly", 0.0)
    if total_subs > 150:
        insights.append(f"Subscriptions total ${total_subs:.0f}/mo (${total_subs * 12:.0f}/yr) — review for unused services")
    if not insights:
        insights.append("Spending patterns look stable — keep tracking to spot trends")
    return insights[:5]


def compute_card_csp_analysis(df: pd.DataFrame, card: dict, today: date | None = None) -> dict:
    """Compute a CSP-specific per-category earn rate and annual value breakdown.

    Args:
        df: Full transactions DataFrame.
        card: Card config dict for the Chase Sapphire Preferred.
        today: Reference date for the trailing 3-month window; defaults to today's date.

    Returns:
        Dict with net_annual_value, gross_rewards, annual_fee, by_category, top_opportunity, fx_note.
    """
    if today is None:
        today = date.today()
    month_list = []
    for i in range(2, -1, -1):
        yr = today.year + (today.month - 1 - i) // 12
        mo = ((today.month - 1 - i) % 12) + 1
        month_list.append(f"{yr:04d}-{mo:02d}")
    annual_fee = card.get("annual_fee", 0)
    empty = {"net_annual_value": -annual_fee, "gross_rewards": 0.0, "annual_fee": annual_fee, "by_category": [], "top_opportunity": "", "fx_note": "CSP has no foreign transaction fees — always use it for international purchases"}
    if df.empty:
        return empty
    expense_df = df[df["amount"] < 0].copy()
    expense_df["month"] = expense_df["date"].dt.strftime("%Y-%m")
    spending = {}
    for cat in expense_df["category"].unique():
        cat_df = expense_df[expense_df["category"] == cat]
        total = float(abs(cat_df[cat_df["month"].isin(month_list)]["amount"].sum()))
        if total > 0:
            spending[cat] = round(total / 3 * 12, 2)
    by_category = []
    gross = 0.0
    for cat, annual_spend in sorted(spending.items(), key=lambda x: x[1], reverse=True):
        earn_rate = card["rewards"].get(cat, card["rewards"].get("Other", 1.0))
        annual_value = compute_card_value_per_category(card, cat, annual_spend)
        note = "No FX fee — always use CSP for international purchases" if cat == "Dubai" else ""
        by_category.append({"category": cat, "monthly_spend": round(annual_spend / 12, 2), "earn_rate": f"{earn_rate:.0f}x", "annual_value": round(annual_value, 2), "note": note})
        gross += annual_value
    gross = round(gross, 2)
    net = round(gross - annual_fee, 2)
    top_opp = ""
    airline_annual = spending.get("Airlines", 0)
    if airline_annual > 0:
        gain = round(airline_annual * (5.0 - 2.0) * card["points_cpp"], 2)
        top_opp = f"Book flights through Chase Travel Portal for 5x (vs 2x direct) — worth ~${gain:.0f}/yr on your airline spend"
    elif any(c["earn_rate"] == "1x" and c["monthly_spend"] > 100 for c in by_category):
        opp = next(c for c in by_category if c["earn_rate"] == "1x" and c["monthly_spend"] > 100)
        top_opp = f"{opp['category']} earns only 1x on CSP (${opp['monthly_spend']:.0f}/mo) — consider a card with bonus in this category"
    return {"net_annual_value": net, "gross_rewards": gross, "annual_fee": annual_fee, "by_category": by_category, "top_opportunity": top_opp, "fx_note": "CSP has no foreign transaction fees — always use it for international purchases"}


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
    mom_changes      = compute_mom_changes(df, today=today)
    category_trends  = compute_category_trends(df, months=3, today=today)
    sub_breakdown    = compute_subscription_breakdown(df, today=today)
    food_breakdown   = compute_food_breakdown(df, today=today)
    fixed_costs      = compute_fixed_costs(df, accounts, today=today)
    lifestyle_insights = compute_lifestyle_insights(df, kpis, fixed_costs, sub_breakdown, today=today)
    health           = compute_health_score(kpis, category_trends, goals, accounts, df, today=today)
    cuts             = compute_actionable_cuts(df, category_trends)
    action_plan      = compute_action_plan(cuts, goals, kpis, today=today)
    spending_pct     = compute_spending_pct_of_income(df, kpis["income"], today=today)
    account_balances = compute_account_balances(accounts)
    top_merchants    = compute_top_merchants(df, this_month)
    card_intel       = compute_card_intelligence(df, cards, today=today)

    csp_card = next((c for c in (cards or {}).get("cards", []) if "sapphire" in c["name"].lower()), None)
    csp_analysis = compute_card_csp_analysis(df, csp_card, today=today) if csp_card else None

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
        "kpis":               kpis,
        "mom_changes":        mom_changes,
        "category_trends":    category_trends,
        "health":             health,
        "cuts":               cuts,
        "action_plan":        action_plan,
        "spending_pct":       spending_pct,
        "account_balances":   account_balances,
        "top_merchants":      top_merchants,
        "trend_labels":       trend_labels,
        "trend_values":       trend_values,
        "goals_display":      goals_display,
        "monthly_streak":     goals.get("monthly_streak", {}),
        "monthly_target":     goals.get("monthly_target", 0.0),
        "card_intel":         card_intel,
        "sub_breakdown":      sub_breakdown,
        "food_breakdown":     food_breakdown,
        "fixed_costs":        fixed_costs,
        "lifestyle_insights": lifestyle_insights,
        "csp_analysis":       csp_analysis,
        "generated_at":       today.strftime("%Y-%m-%d"),
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


def compute_health_score(kpis: dict, category_trends: list, goals: dict, accounts: dict, df: pd.DataFrame, today: date | None = None) -> dict:
    """Compute a 0–100 financial health score across six weighted dimensions.

    Args:
        kpis: KPI dict as returned by compute_kpis.
        category_trends: Category trend list as returned by compute_category_trends.
        goals: Goals config dict.
        accounts: Accounts config dict with an "accounts" list of account objects.
        df: Full transactions DataFrame.
        today: Reference date for calculations; defaults to today's date.

    Returns:
        A dict with score (int), grade (str), dimensions (list), passing (list[str]), and failing (list[str]).
    """
    if today is None:
        today = date.today()
    dimensions = []
    total = 0.0
    passing = []
    failing = []

    income = kpis["income"]
    expenses = kpis["expenses"]

    # Dim 1: Income coverage (25 pts)
    if income == 0:
        d1 = 10; st1 = "warn"; ex1 = "No income recorded this month — check statement coverage"
    elif expenses <= income:
        d1 = 25; st1 = "pass"; ex1 = f"Expenses (${expenses:,.0f}) are below income (${income:,.0f}) — positive cash flow"
    else:
        ratio = (expenses - income) / income
        d1 = max(0, round(25 - ratio * 50)); st1 = "fail" if d1 == 0 else "warn"
        ex1 = f"Expenses exceeded income by {ratio*100:.0f}% this month"
    dimensions.append({"label": "Income coverage", "score": d1, "max": 25, "status": st1, "explanation": ex1})
    total += d1
    if st1 == "pass": passing.append("Income coverage")
    elif d1 == 0: failing.append("Income coverage")

    # Dim 2: Savings rate (20 pts)
    if income <= 0:
        d2 = 0; st2 = "fail"; ex2 = "No income this month — savings rate cannot be calculated"
    else:
        sr = kpis["savings_rate"]
        d2 = round(min(sr / 0.20, 1.0) * 20) if sr > 0 else 0
        if d2 >= 18: st2 = "pass"; ex2 = f"Savings rate {sr*100:.1f}% — on track for the 20% target"
        elif d2 >= 8: st2 = "warn"; ex2 = f"Savings rate {sr*100:.1f}% — aim for 20% to build wealth"
        else: st2 = "fail"; ex2 = f"Savings rate {sr*100:.1f}% — expenses are consuming most of income"
    dimensions.append({"label": "Savings rate", "score": d2, "max": 20, "status": st2, "explanation": ex2})
    total += d2
    if st2 == "pass": passing.append("Savings rate")
    elif d2 == 0: failing.append("Savings rate")

    # Dim 3: Debt burden (15 pts)
    credit_bal = abs(sum(a["balance"] for a in accounts.get("accounts", []) if a["balance"] < 0))
    liquid = sum(a["balance"] for a in accounts.get("accounts", []) if a.get("type") in ["checking", "savings"] and a["balance"] > 0)
    if liquid == 0:
        d3 = 3; st3 = "warn"; ex3 = "No liquid assets tracked — add checking/savings accounts"
    else:
        dr = credit_bal / liquid
        if dr < 0.10: d3 = 15; st3 = "pass"; ex3 = f"Credit balance ${credit_bal:,.0f} is only {dr*100:.0f}% of liquid savings"
        elif dr < 0.25: d3 = 8; st3 = "warn"; ex3 = f"Credit balance ${credit_bal:,.0f} is {dr*100:.0f}% of liquid savings — aim to pay it down"
        elif dr < 0.50: d3 = 3; st3 = "warn"; ex3 = f"Credit balance ${credit_bal:,.0f} is {dr*100:.0f}% of liquid savings — high debt burden"
        else: d3 = 0; st3 = "fail"; ex3 = f"Credit balance ${credit_bal:,.0f} exceeds 50% of liquid savings — prioritize payoff"
    dimensions.append({"label": "Debt burden", "score": d3, "max": 15, "status": st3, "explanation": ex3})
    total += d3
    if st3 == "pass": passing.append("Debt burden")
    elif d3 == 0: failing.append("Debt burden")

    # Dim 4: Fixed cost ratio (15 pts)
    fixed = compute_fixed_costs(df, accounts, today=today)
    pct = fixed["pct_of_income"]
    if fixed["avg_income"] == 0:
        d4 = 8; st4 = "warn"; ex4 = "Avg income unclear — fixed cost ratio cannot be calculated"
    elif pct < 0.40:
        d4 = 15; st4 = "pass"; ex4 = f"Fixed costs (rent, phone, insurance) are {pct*100:.0f}% of income — healthy"
    elif pct < 0.55:
        d4 = 8; st4 = "warn"; ex4 = f"Fixed costs are {pct*100:.0f}% of income — leaves little room for savings"
    else:
        d4 = 0; st4 = "fail"; ex4 = f"Fixed costs are {pct*100:.0f}% of income — above 55% is a financial stress zone"
    dimensions.append({"label": "Fixed cost ratio", "score": d4, "max": 15, "status": st4, "explanation": ex4})
    total += d4
    if st4 == "pass": passing.append("Fixed cost ratio")
    elif d4 == 0: failing.append("Fixed cost ratio")

    # Dim 5: Emergency fund (15 pts)
    if expenses == 0:
        d5 = 15; st5 = "pass"; ex5 = "No expense data — emergency fund assumed adequate"
    else:
        ratio5 = liquid / (expenses * 3)
        if ratio5 >= 1.0: d5 = 15; st5 = "pass"; ex5 = f"Liquid savings cover {ratio5:.1f}x three months of expenses — excellent buffer"
        elif ratio5 >= 0.33: d5 = 8; st5 = "warn"; ex5 = f"Liquid savings cover {ratio5*3:.1f} months of expenses — target is 3 months"
        else: d5 = 0; st5 = "fail"; ex5 = "Liquid savings cover less than 1 month of expenses — build an emergency fund"
    dimensions.append({"label": "Emergency fund", "score": d5, "max": 15, "status": st5, "explanation": ex5})
    total += d5
    if st5 == "pass": passing.append("Emergency fund")
    elif d5 == 0: failing.append("Emergency fund")

    # Dim 6: Investment rate (10 pts)
    this_month = today.strftime("%Y-%m")
    inv_amt = 0.0
    if not df.empty:
        inv_df = df[(df["category"] == "Investments") & (df["amount"] < 0) & (df["date"].dt.strftime("%Y-%m") == this_month)]
        inv_amt = abs(float(inv_df["amount"].sum()))
    if income <= 0:
        d6 = 5; st6 = "warn"; ex6 = "No income data — investment rate unknown"
    elif inv_amt == 0:
        d6 = 0; st6 = "fail"; ex6 = "No investments recorded this month — consider contributing to a brokerage"
    else:
        ir = inv_amt / income
        if ir >= 0.05: d6 = 10; st6 = "pass"; ex6 = f"Investing {ir*100:.0f}% of income this month — great habit"
        else: d6 = 5; st6 = "warn"; ex6 = f"Investing {ir*100:.0f}% of income — aim for 5%+ to grow wealth"
    dimensions.append({"label": "Investment rate", "score": d6, "max": 10, "status": st6, "explanation": ex6})
    total += d6
    if st6 == "pass": passing.append("Investment rate")
    elif d6 == 0: failing.append("Investment rate")

    score = round(min(100.0, total))
    return {"score": score, "grade": _score_to_grade(score), "dimensions": dimensions, "passing": passing, "failing": failing}


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
