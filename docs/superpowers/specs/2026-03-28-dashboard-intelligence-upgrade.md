# Dashboard Intelligence Upgrade — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the finance dashboard from a generic spending summary into a personalized, intelligent financial advisor that surfaces rent, subscription redundancies, restaurant breakdowns, a meaningful health score, and Chase Sapphire Preferred card optimization.

**Architecture:** All analytics changes go into `dashboard/analytics.py` as new/replaced compute functions. `build_context()` passes new context keys to the Jinja2 template. Card data lives in `data/cards.json`. The existing 5-tab layout is preserved; new panels are added inside the Spending, Insights, and Cards tabs.

**Tech Stack:** Python, pandas, Jinja2, Chart.js, DaisyUI/Alpine.js (existing stack, no new deps)

---

## 1. New Analytics Functions

### 1a. `compute_subscription_breakdown(df: pd.DataFrame, today: date | None = None) -> dict`

Returns all recurring subscription services with per-service cost and redundancy flags.

**Logic:**
```python
# Filter subscriptions from trailing 3 months
expense_df = df[(df["category"] == "Subscriptions") & (df["amount"] < 0)]
# Build trailing 3-month list (same pattern as compute_category_trends)
# Group by merchant, compute avg monthly cost = total / months_present
# Detect phone redundancy: count merchants matching any of
#   ["t-mobile", "tmobile", "visible", "verizon", "straight talk"]
# If phone_count >= 2: mark each matching service with redundant=True
# redundancy_waste = sum of monthly cost for all but the most expensive phone service
```

**Output shape:**
```python
{
  "services": [
    {"name": "WeWork", "monthly": 49.00, "annual": 588.00, "redundant": False},
    {"name": "T-Mobile prepaid", "monthly": 15.47, "annual": 185.64, "redundant": True},
    {"name": "Visible", "monthly": 25.00, "annual": 300.00, "redundant": True},
  ],
  "total_monthly": 213.45,
  "total_annual": 2561.40,
  "redundancy_waste": 40.47   # monthly savings if cheapest duplicate phone plan cancelled
}
```

### 1b. `compute_food_breakdown(df: pd.DataFrame, today: date | None = None) -> list`

Returns Food & Dining transactions broken down by merchant for the trailing 3 months.

**Logic:**
```python
# Filter category == "Food & Dining", amount < 0, trailing 3 months
# Group by merchant: total spend (abs), visit count, avg ticket = total/count
# Sort by total descending, return top 15
```

**Output shape:**
```python
[{"name": "Chipotle", "total": 145.20, "visits": 8, "avg_ticket": 18.15}, ...]
```

### 1c. `compute_fixed_costs(df: pd.DataFrame, accounts: dict, today: date | None = None) -> dict`

Identifies fixed monthly obligations and their ratio to 3-month average income.

**Logic:**
```python
# Build trailing 3-month list
# Rent: avg monthly spend in category "Housing" over 3 months
# Phone: avg monthly spend in category "Phone & Cell" over 3 months
# Insurance: avg monthly spend in category "Insurance" over 3 months
# Subscriptions: total_monthly from compute_subscription_breakdown
# avg_income: avg monthly income (positive transactions) over trailing 3 months
#   (uses 3-month average to avoid distortion from low-data months)
# pct_of_income = total_fixed / avg_income if avg_income > 0 else 0.0
```

**Output shape:**
```python
{
  "rent": 1314.00,
  "phone": 56.93,
  "insurance": 19.50,
  "subscriptions": 213.45,
  "total": 1603.88,
  "avg_income": 4692.00,   # 3-month avg monthly income
  "pct_of_income": 0.34    # fraction
}
```

### 1d. `compute_lifestyle_insights(df: pd.DataFrame, kpis: dict, fixed_costs: dict, sub_breakdown: dict, today: date | None = None) -> list`

Generates 3–5 personalized, actionable insight strings. Evaluates rules in priority order; always returns at least 1 insight.

**Rules (evaluated in this order, max 5 insights returned):**
```python
insights = []

# Rule 1: Phone redundancy
phone_waste = sub_breakdown.get("redundancy_waste", 0)
if phone_waste > 0:
    insights.append(f"You have multiple active phone plans — cancelling the cheapest saves ~${phone_waste*12:.0f}/yr")

# Rule 2: Rent burden (using avg_income from fixed_costs)
if fixed_costs["avg_income"] > 0:
    rent_pct = fixed_costs["rent"] / fixed_costs["avg_income"]
    if rent_pct > 0.33:
        target = fixed_costs["avg_income"] * 0.30
        insights.append(f"Rent is {rent_pct*100:.0f}% of income — the 30% rule suggests ${target:,.0f}/mo")

# Rule 3: International/Dubai FX opportunity
dubai_3mo = abs(df[(df["category"]=="Dubai") & (df["amount"]<0) ...trailing 3mo...]["amount"].sum()) / 3
if dubai_3mo > 300:
    fx_savings = round(dubai_3mo * 0.03 * 12)
    insights.append(f"International spending averages ${dubai_3mo:.0f}/mo — CSP has no FX fee, saving ~${fx_savings}/yr vs cards with 3% foreign fee")

# Rule 4: Dining out cost
food_3mo = abs(df[(df["category"]=="Food & Dining") & (df["amount"]<0) ...]["amount"].sum()) / 3
if food_3mo > 500:
    savings = round(food_3mo * 0.20)
    insights.append(f"Dining out costs ${food_3mo:.0f}/mo — cooking at home 2 extra nights/week could save ~${savings}/mo")

# Rule 5: High subscriptions
if sub_breakdown["total_monthly"] > 150:
    insights.append(f"Subscriptions total ${sub_breakdown['total_monthly']:.0f}/mo (${sub_breakdown['total_annual']:.0f}/yr) — review for unused services")

# Fallback (always add if insights < 3)
if len(insights) < 1:
    insights.append("Spending patterns look stable — keep tracking to spot trends")

return insights[:5]
```

---

## 2. Health Score Redesign

Replace existing `compute_health_score` with 6-dimension system. All derived values come from existing data:
- `credit_balance` = `abs(sum(a["balance"] for a in accounts["accounts"] if a["balance"] < 0))` (computed inside the function from accounts dict)
- `liquid_assets` = `sum(a["balance"] for a in accounts["accounts"] if a.get("type") in ["checking","savings"] and a["balance"] > 0)`
- `monthly_investments` = `abs(df[(df["category"]=="Investments") & (df["amount"]<0) & (df["date"].dt.strftime("%Y-%m")==this_month)]["amount"].sum())`

### Signature
```python
def compute_health_score(kpis: dict, category_trends: list, goals: dict,
                         accounts: dict, df: pd.DataFrame,
                         today: date | None = None) -> dict:
```

**Note:** Adds `accounts` and `df` parameters vs current signature. `build_context()` already has both — update the call site.

### Dimensions

| # | Label | Max | Formula |
|---|-------|-----|---------|
| 1 | Income coverage | 25 | `25` if `expenses ≤ income`, else `max(0, 25 - (expenses-income)/income * 50)` |
| 2 | Savings rate | 20 | `min(savings_rate / 0.20, 1.0) * 20` |
| 3 | Debt burden | 15 | if `liquid>0`: `debt_ratio = credit_balance/liquid`; 15 if <0.10, 8 if <0.25, 3 if <0.50, else 0 |
| 4 | Fixed cost ratio | 15 | from `fixed_costs["pct_of_income"]`: 15 if <0.40, 8 if <0.55, 0 if ≥0.55; if avg_income==0: 8 |
| 5 | Emergency fund | 15 | `liquid_assets / (kpis["expenses"]*3)`: 15 if ≥1.0, 8 if ≥0.33, 0 otherwise |
| 6 | Investment rate | 10 | 10 if `monthly_investments/income ≥ 0.05`, 5 if >0, 0 otherwise |

**Output shape:**
```python
{
  "score": 62,
  "grade": "C",
  "dimensions": [
    {"label": "Income coverage", "score": 18, "max": 25, "status": "warn",
     "explanation": "Expenses exceeded income by 15% this month"},
    {"label": "Savings rate", "score": 0, "max": 20, "status": "fail",
     "explanation": "Negative savings this month — expenses > income"},
    {"label": "Debt burden", "score": 8, "max": 15, "status": "warn",
     "explanation": "Credit balance is $2,581 — 10% of liquid assets"},
    {"label": "Fixed cost ratio", "score": 8, "max": 15, "status": "warn",
     "explanation": "Fixed costs are 34% of income — near the 40% caution zone"},
    {"label": "Emergency fund", "score": 15, "max": 15, "status": "pass",
     "explanation": "Liquid savings cover 13x monthly expenses — excellent"},
    {"label": "Investment activity", "score": 10, "max": 10, "status": "pass",
     "explanation": "Investing 18% of income this month"},
  ],
  "passing": ["Emergency fund", "Investment activity"],
  "failing": ["Savings rate"],
}
```

Status values: `"pass"` (full points), `"warn"` (partial), `"fail"` (0).

---

## 3. Chase Sapphire Preferred — Cards Data

### `data/cards.json` entry
```json
{
  "cards": [{
    "name": "Chase Sapphire Preferred",
    "issuer": "Chase",
    "annual_fee": 95,
    "reward_type": "points",
    "points_cpp": 0.015,
    "rewards": {
      "Food & Dining": 3.0,
      "Subscriptions": 3.0,
      "Travel": 2.0,
      "Airlines": 2.0,
      "Transport": 2.0,
      "Shopping": 1.0,
      "Health": 1.0,
      "Entertainment": 1.0,
      "Dubai": 1.0,
      "Insurance": 1.0,
      "Phone & Cell": 1.0,
      "Housing": 1.0,
      "Other": 1.0
    }
  }]
}
```

### `core/cards.py` — CURATED_CARDS update
Every card in `CURATED_CARDS` gains these additional category keys (defaulting to the card's `"Other"` rate for all new categories that aren't special for that card):

New categories to add to every curated card: `Airlines`, `Travel`, `Dubai`, `Entertainment`, `Phone & Cell`, `Insurance`, `Housing`.

Special overrides:
- Capital One Venture X: `Airlines: 5.0, Travel: 5.0` (its main value prop)
- Amex Gold: `Travel: 1.0, Airlines: 1.0` (no bonus on travel — Amex Platinum is the travel card)
- Chase Freedom Unlimited: `Travel: 1.5, Airlines: 1.5` (same as its baseline)

### `compute_card_csp_analysis(df: pd.DataFrame, card: dict, today: date | None = None) -> dict`

CSP-specific breakdown showing per-category earn rates and annual values.

**Logic:**
```python
# Build annualised spending by category (same as compute_card_intelligence)
# For each category with spending > 0:
#   annual_value = compute_card_value_per_category(card, cat, annual_spend)
#   earn_rate_str = f"{card['rewards'].get(cat, card['rewards']['Other']):.0f}x"
# Special note for Dubai: append "no FX fee" note
# top_opportunity: find category where switching from 1x to higher rate saves most
# Compute net_annual_value = sum(annual_values) - card["annual_fee"]
```

**Output shape:**
```python
{
  "net_annual_value": 312.00,
  "gross_rewards": 407.00,
  "annual_fee": 95,
  "by_category": [
    {"category": "Food & Dining", "monthly_spend": 807, "earn_rate": "3x",
     "annual_value": 435, "note": ""},
    {"category": "Dubai", "monthly_spend": 718, "earn_rate": "1x",
     "annual_value": 129, "note": "No FX fee — always use CSP for international"},
  ],
  "top_opportunity": "Book flights through Chase Travel Portal for 5x (vs 2x direct) — worth ~$X/yr on your airline spend",
  "fx_note": "CSP has no foreign transaction fees — always use it abroad"
}
```

`annual_value` per category = `compute_card_value_per_category(card, cat, annual_spend)` (already in cards.py).

---

## 4. `build_context()` — Integration

Add these calls and context keys:

```python
sub_breakdown    = compute_subscription_breakdown(df, today=today)
food_breakdown   = compute_food_breakdown(df, today=today)
fixed_costs      = compute_fixed_costs(df, accounts, today=today)
lifestyle_insights = compute_lifestyle_insights(df, kpis, fixed_costs, sub_breakdown, today=today)
# replace existing health call:
health           = compute_health_score(kpis, category_trends, goals, accounts, df, today=today)
# csp_analysis (only if cards configured):
csp_card = next((c for c in (cards or {}).get("cards", []) if "sapphire" in c["name"].lower()), None)
csp_analysis     = compute_card_csp_analysis(df, csp_card, today=today) if csp_card else None
```

New context keys returned: `sub_breakdown`, `food_breakdown`, `fixed_costs`, `lifestyle_insights`, `csp_analysis`.

---

## 5. Dashboard Template — Panel Placement

### Spending tab (existing tab, add panels after existing category chart)
1. **Fixed Costs panel** — table: Rent / Phone / Insurance / Subscriptions rows + Total row + pct of income
2. **Subscriptions panel** — list: service name, monthly cost, annual cost; 🔴 badge if `redundant`; total row
3. **Food & Dining breakdown panel** — table: restaurant, visits, avg ticket, 3-month total; top 10

### Insights tab (existing tab, replace health score card + add lifestyle panel)
4. **Health Score card** — replace single score with 6-row dimension table: label, score/max bar, status icon, explanation text
5. **Lifestyle Insights panel** — bulleted list of `lifestyle_insights` strings (3–5 items)

### Cards tab (existing tab, add above upgrade recommendations)
6. **CSP Analysis panel** — shown only if `csp_analysis` is not None; per-category earn rate table + top opportunity callout + FX note

---

## 6. Testing Strategy

All tests go in `tests/test_dashboard.py`. Key test cases:

```python
# compute_subscription_breakdown
def test_subscription_breakdown_detects_phone_redundancy():
    # df with t-mobile + visible both in Subscriptions
    # assert result["redundancy_waste"] > 0
    # assert sum(1 for s in result["services"] if s["redundant"]) == 2

def test_subscription_breakdown_no_redundancy():
    # single phone service → redundancy_waste == 0

def test_subscription_breakdown_empty_df():
    # returns {"services": [], "total_monthly": 0, ...}

# compute_food_breakdown
def test_food_breakdown_groups_by_merchant():
    # two chipotle transactions → one entry with visits=2

def test_food_breakdown_empty():
    # returns []

# compute_fixed_costs
def test_fixed_costs_rent_detected():
    # Housing category transaction → rent field populated

def test_fixed_costs_pct_of_income_uses_3mo_avg():
    # 3 months of income data → pct uses avg, not current month

# compute_lifestyle_insights
def test_lifestyle_phone_redundancy_rule():
    # sub_breakdown with redundancy_waste=40 → insight about phone plans

def test_lifestyle_rent_burden_rule():
    # fixed_costs rent=1400, avg_income=2000 → rent burden insight (70%)

def test_lifestyle_fallback_always_returns_something():
    # all conditions false → still returns 1 insight

# compute_health_score (new signature)
def test_health_score_income_coverage_full_points():
    # expenses < income → dimension score == 25

def test_health_score_no_income_handled():
    # income == 0 → no ZeroDivisionError, returns valid dict

def test_health_score_returns_dimensions_list():
    # result["dimensions"] has 6 items

def test_health_score_score_is_sum_of_dimensions():
    # result["score"] == sum(d["score"] for d in result["dimensions"])

# compute_card_csp_analysis
def test_csp_analysis_returns_by_category():
    # card with known rewards → by_category list populated

def test_csp_analysis_net_value_equals_gross_minus_fee():
    # net_annual_value == gross_rewards - annual_fee
```

---

## 7. Files Modified

| File | Change |
|------|--------|
| `dashboard/analytics.py` | Add `compute_subscription_breakdown`, `compute_food_breakdown`, `compute_fixed_costs`, `compute_lifestyle_insights`, `compute_card_csp_analysis`; replace `compute_health_score` (new signature); update `build_context()` |
| `dashboard/renderer.py` | No change needed — `build_context()` return dict flows through automatically |
| `templates/dashboard.html.j2` | Add 6 new panels in Spending/Insights/Cards tabs |
| `data/cards.json` | Create with Chase Sapphire Preferred entry |
| `core/cards.py` | Update `CURATED_CARDS` reward maps to include 7 new category keys |
| `tests/test_dashboard.py` | Add ~15 new test cases; update `compute_health_score` tests for new signature |
