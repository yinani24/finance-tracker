# Dashboard Context Reference

The dashboard is a two-module pipeline: `dashboard.py` loads raw data files and invokes `dashboard_data.py` which computes every KPI, trend, and score. The result is a single `context` dict passed to the Jinja2 template. This document is the authoritative reference for every key in that dict.

---

## Pipeline Overview

```
data/
  transactions.csv   ──┐
  accounts.json      ──┤  dashboard._load_files()
  goals.json         ──┘
         │
         ▼
  build_context(df, accounts, goals)   ← dashboard_data.py
         │
         ▼
  context dict   ──→   dashboard.html.j2   ──→   reports/dashboard.html
```

`build_dashboard()` in `dashboard.py` is the only public entry point. It calls `_load_files()` to read the three data files, then calls `build_context()` to produce the context dict, then renders the Jinja2 template with that context plus three inlined assets (Chart.js, DaisyUI CSS, Alpine.js).

---

## build_context() — Top-Level Function

**Module:** `dashboard_data.py`

**Signature:**

```python
def build_context(
    df: pd.DataFrame,
    accounts: dict,
    goals: dict,
    today: date | None = None,
) -> dict:
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `df` | `pd.DataFrame` | Full transactions DataFrame. Must have `date`, `amount`, `category`, `merchant` columns. `date` must be a parsed datetime column (not raw string). |
| `accounts` | `dict` | Accounts dict as loaded from `accounts.json`. Must have an `"accounts"` key with a list of account objects. |
| `goals` | `dict` | Goals dict as loaded from `goals.json`. Must have `"monthly_target"`, `"goals"`, and `"monthly_streak"` keys. |
| `today` | `date \| None` | Reference date for all month-relative calculations. Defaults to `date.today()`. Pass a fixed date in tests to make assertions deterministic. |

**Returns:** A dict with the keys documented below.

---

## Context Keys Reference

### `kpis` — Current-Month KPIs

**Type:** `dict`

**Computed by:** `compute_kpis(df, accounts, goals, today)`

| Key | Type | Description |
|-----|------|-------------|
| `net_worth` | `float` | Sum of all account balances (can be negative if credit > assets) |
| `income` | `float` | Total positive-amount transactions this month (rounded to 2 dp) |
| `expenses` | `float` | Absolute value of all negative-amount transactions this month |
| `saved` | `float` | `income - expenses` (can be negative) |
| `monthly_target` | `float` | Monthly savings target from `goals.monthly_target` |
| `savings_rate` | `float` | `saved / income` if `income > 0`, else `0.0` |
| `this_month` | `str` | Current month in `YYYY-MM` format |

**Zero-state:** When `df` is empty all monetary fields are `0.0`; `this_month` is still populated.

---

### `category_trends` — 3-Month Category Breakdown

**Type:** `list[dict]`

**Computed by:** `compute_category_trends(df, months=3, today)`

Each dict represents one spending category present in the trailing 3-month window:

| Key | Type | Description |
|-----|------|-------------|
| `name` | `str` | Category name (e.g. `"Food & Dining"`) |
| `current_amount` | `float` | Absolute spend this month |
| `prior_amounts` | `list[float]` | Spend amounts for the 2 preceding months, oldest first |
| `pct_change` | `float` | `(current - prior) / prior` where prior = last month. `0.0` if no prior data. |
| `direction` | `str` | `"up"` if pct_change > 5%, `"down"` if < −5%, `"flat"` otherwise |

**Zero-state:** Returns `[]` when `df` is empty.

**Ordering:** Categories appear in alphabetical order by name.

---

### `health` — Financial Health Score

**Type:** `dict`

**Computed by:** `compute_health_score(kpis, category_trends, goals)`

| Key | Type | Description |
|-----|------|-------------|
| `score` | `int` | 0–100 composite score (see scoring breakdown below) |
| `grade` | `str` | Letter grade derived from score |
| `passing` | `list[str]` | Dimensions where the user is performing well |
| `failing` | `list[str]` | Dimensions where the user needs improvement |

#### Scoring Breakdown

| Dimension | Max Points | Criteria |
|-----------|-----------|----------|
| Savings rate | 30 | Linear: 30 pts at 20%+ savings rate, 0 pts at 0% |
| Spending trends | 25 | 25 pts if no category up >20% MoM; −8 pts per offending category |
| Goal progress | 25 | 25 pts if no at-risk goals; −12 pts per at-risk goal |
| Subscription ratio | 10 | 10 pts if subscriptions < 8% of income; 5 pts if 8–15%; 0 pts if >15% |
| Emergency fund | 10 | 10 pts if emergency fund ≥50% funded; 5 pts if no emergency fund goal |

#### Grade Thresholds

| Score | Grade |
|-------|-------|
| 90–100 | A |
| 80–89 | B+ |
| 75–79 | B |
| 60–74 | C |
| 45–59 | D |
| 0–44 | F |

---

### `cuts` — Actionable Spending Cuts

**Type:** `list[dict]`

**Computed by:** `compute_actionable_cuts(df, category_trends)`

Each dict represents one recommended spending reduction:

| Key | Type | Description |
|-----|------|-------------|
| `category` | `str` | Category name |
| `description` | `str` | Short human-readable description (e.g. `"Food & Dining is up 23% vs 3-month average"`) |
| `detail` | `str` | Longer supporting detail with dollar figures |
| `potential_saving` | `float` | Estimated monthly saving in dollars |
| `icon` | `str` | Emoji icon for the category |

**Ordering:** Sorted by `potential_saving` descending (highest-impact cut first).

**Zero-state:** Returns `[]` when `df` is empty or `category_trends` is empty.

#### Cut Logic

- **Subscriptions:** Lists individual merchants ≥ $15/mo. One cut item covers all qualifying subscriptions, not one per merchant.
- **General categories:** Flagged when current month spend > 3-month average × 1.15.
- **Transport ride-count:** Additional check — if average monthly ride count > 10, a "walk short trips" suggestion is added (only if Transport wasn't already flagged via the general path).

---

### `action_plan` — 3-Step Action Plan

**Type:** `list[dict]`

**Computed by:** `compute_action_plan(cuts, goals, kpis, today)`

Up to 3 steps derived from the top 3 entries in `cuts`:

| Key | Type | Description |
|-----|------|-------------|
| `step` | `int` | Step number (1, 2, 3) |
| `month_label` | `str` | Target month for this step (e.g. `"March 2026"`) |
| `action` | `str` | Short action title (e.g. `"Reduce Food & Dining spending"`) |
| `saving` | `float` | Potential monthly saving from this step |
| `goal_link` | `str \| None` | Name of highest-priority at-risk goal (Step 1 only); `None` for steps 2–3 |
| `description` | `str` | Full sentence description with amount and optional goal link |

**Step month assignment:** Step 1 = current month, Step 2 = next month, Step 3 = month after.

**Zero-state:** Returns `[]` when `cuts` is empty.

---

### `spending_pct` — Category Spend as % of Income

**Type:** `list[dict]`

**Computed by:** `compute_spending_pct_of_income(df, kpis["income"], today)`

Each dict represents one spending category for the current month:

| Key | Type | Description |
|-----|------|-------------|
| `name` | `str` | Category name |
| `amount` | `float` | Absolute spend this month |
| `pct_of_income` | `float` | `(amount / income) × 100`, rounded to 1 dp |

**Ordering:** Sorted by `amount` descending.

**Zero-state:** Returns `[]` when `df` is empty, income ≤ 0, or no expenses exist this month.

---

### `account_balances` — Per-Account Balance Breakdown

**Type:** `list[dict]`

**Computed by:** `compute_account_balances(accounts)`

Each dict represents one account:

| Key | Type | Description |
|-----|------|-------------|
| `name` | `str` | Account name (e.g. `"Chase-CreditCard"`) |
| `balance` | `float` | Current balance (negative for credit cards with outstanding debt) |
| `type` | `str` | Account type: `checking`, `savings`, `credit`, or `investment` |
| `share_of_total` | `float` | `balance / total_positive_balances` as a fraction (0–1). `0.0` for negative-balance accounts. |

**Zero-state:** Returns `[]` when no accounts are present.

---

### `top_merchants` — Top 10 Merchants This Month

**Type:** `list[dict]`

**Computed by:** `compute_top_merchants(df, this_month)`

Each dict represents one merchant:

| Key | Type | Description |
|-----|------|-------------|
| `name` | `str` | Normalized merchant name |
| `amount` | `float` | Absolute total spend at this merchant this month |
| `category` | `str` | Category of the first transaction at this merchant this month |
| `tx_count` | `int` | Number of transactions at this merchant this month |

**Ordering:** Sorted by `amount` descending. Limited to top 10.

**Zero-state:** Returns `[]` when `df` is empty or no expenses exist this month.

---

### `trend_labels` and `trend_values` — 12-Month Spending Trend

**Type:** `list[str]` and `list[float]`

**Computed by:** inline in `build_context()`

Parallel lists representing the last 12 calendar months:

- `trend_labels`: Month strings in `YYYY-MM` format, oldest first (e.g. `["2025-04", ..., "2026-03"]`)
- `trend_values`: Total absolute expense for each month (expenses only, no income). `0.0` for months with no data.

These are used to power the Chart.js line chart on the Overview tab.

---

### `goals_display` — Goals for the Goals Tab

**Type:** `list[dict]`

**Computed by:** inline in `build_context()` from `goals["goals"]`

Each dict represents one named goal:

| Key | Type | Description |
|-----|------|-------------|
| `name` | `str` | Goal name |
| `pct` | `int` | Percentage complete (0–100) |
| `current` | `float` | Amount saved so far |
| `target` | `float` | Total target amount |
| `deadline` | `str` | Deadline in `YYYY-MM` format |
| `created` | `str` | Creation date in `YYYY-MM-DD` format (empty string if missing) |

**Zero-state:** Empty list if no named goals are configured.

---

### `monthly_streak` — Monthly Savings Streak

**Type:** `dict`

Passed through directly from `goals["monthly_streak"]`.

| Key | Type | Description |
|-----|------|-------------|
| `current` | `int` | Number of consecutive months the savings target was met |
| `best` | `int` | All-time best streak length |

**Default:** `{}` if not present in `goals.json`.

---

### `monthly_target` — Monthly Savings Target

**Type:** `float`

Passed through directly from `goals["monthly_target"]`. Represents the user's configured monthly savings target in dollars.

**Default:** `0.0` if not configured.

---

### `generated_at` — Report Generation Date

**Type:** `str`

The `today` date in `YYYY-MM-DD` format. Used in the dashboard footer to show when the report was generated.

---

## Template Rendering

The Jinja2 template at `templates/dashboard.html.j2` receives the full context dict via `**context`, plus three additional keys:

| Key | Description |
|-----|-------------|
| `chartjs` | Contents of `templates/chart.min.js` (inlined to make the HTML self-contained) |
| `daisyui_css` | Contents of `templates/daisyui.min.css` (inlined) |
| `alpine_js` | Contents of `templates/alpine.min.js` (inlined) |

The `format_currency` Jinja2 filter is registered by `build_dashboard()`: `{{ value | format_currency }}` renders a float as `1,234.56`.

---

## Zero-State Behavior

When data files are missing or empty:

| Missing file | Effect |
|-------------|--------|
| `transactions.csv` absent | `df` is an empty DataFrame; all trend/KPI monetary fields are `0.0` |
| `accounts.json` absent | `accounts = {"accounts": []}`, `net_worth = 0.0`, `account_balances = []` |
| `goals.json` absent | `goals = {"monthly_target": 0.0, "goals": [], "monthly_streak": {}}`, health score uses partial-credit defaults |

The template is designed to render a valid (though empty-state) HTML page in all cases. No exceptions are raised for missing data.

---

## Testing the Data Layer

`dashboard_data.py` is fully unit-testable without touching the filesystem. Pass synthetic DataFrames and dicts directly:

```python
import pandas as pd
from datetime import date
from dashboard_data import build_context

df = pd.DataFrame([
    {"date": pd.Timestamp("2026-03-10"), "amount": -50.0,
     "merchant": "chipotle", "category": "Food & Dining",
     "account": "Chase-CreditCard", "source": "manual",
     "is_income": False, "is_savings": False, "notes": ""},
    {"date": pd.Timestamp("2026-03-15"), "amount": 3000.0,
     "merchant": "payroll", "category": "Income",
     "account": "BofA-1234", "source": "manual",
     "is_income": True, "is_savings": False, "notes": ""},
])
accounts = {"accounts": [{"name": "BofA-1234", "balance": 4000.0, "type": "checking"}]}
goals = {"monthly_target": 500.0, "goals": [], "monthly_streak": {"current": 2, "best": 4}}

ctx = build_context(df, accounts, goals, today=date(2026, 3, 26))
assert ctx["kpis"]["income"] == 3000.0
assert ctx["kpis"]["expenses"] == 50.0
assert ctx["health"]["score"] > 0
```

See `tests/test_dashboard_data.py` for the full test suite.
