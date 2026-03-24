# Finance Dashboard UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the finance dashboard with a top-tab layout (Overview/Spending/Goals/Insights), a pure-function computation layer (`dashboard_data.py`), financial health scoring, actionable cut recommendations, and a 3-month action plan — all built test-first.

**Architecture:** `dashboard_data.py` holds all computation as pure, side-effect-free functions. `dashboard.py` is reduced to file I/O + render. The Jinja2 template is rewritten using DaisyUI v4 (inlined CSS) + Alpine.js (inlined JS) + Chart.js (already inlined). All new logic is written test-first — every test is written and confirmed to fail before the implementation is written.

**Tech Stack:** Python 3.10+, pandas, Jinja2, pytest, DaisyUI v4 (standalone CSS), Alpine.js v3.14, Chart.js (existing)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `dashboard_data.py` | CREATE | All computation — KPIs, trends, health score, cuts, action plan |
| `dashboard.py` | MODIFY | Thin renderer: file I/O + calls `build_context` + Jinja2 render |
| `templates/dashboard.html.j2` | REWRITE | 4-tab UI with DaisyUI + Alpine.js |
| `templates/daisyui.min.css` | CREATE | DaisyUI v4 standalone CSS, downloaded once, inlined at render |
| `templates/alpine.min.js` | CREATE | Alpine.js v3.14 minified, downloaded once, inlined at render |
| `tests/test_dashboard_data.py` | CREATE | TDD unit tests for all `dashboard_data.py` functions |
| `tests/test_dashboard.py` | MODIFY | Update integration tests for new template structure |

---

## Chunk 1: Download Static Assets

### Task 1: Download DaisyUI v4 and Alpine.js

**Files:**
- Create: `templates/daisyui.min.css`
- Create: `templates/alpine.min.js`

- [ ] **Step 1: Download DaisyUI v4 standalone CSS**

```bash
curl -sL "https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.css" -o templates/daisyui.min.css
```

Expected: file created, size ~600KB (unminified DaisyUI v4 full bundle).

- [ ] **Step 2: Verify DaisyUI file is non-empty and contains CSS**

```bash
wc -c templates/daisyui.min.css
head -c 200 templates/daisyui.min.css
```

Expected: size > 100000 bytes, content starts with CSS.

- [ ] **Step 3: Download Alpine.js v3.14**

```bash
curl -sL "https://unpkg.com/alpinejs@3.14.8/dist/cdn.min.js" -o templates/alpine.min.js
```

- [ ] **Step 4: Verify Alpine.js file**

```bash
wc -c templates/alpine.min.js
head -c 100 templates/alpine.min.js
```

Expected: size ~45000 bytes, content starts with JS.

- [ ] **Step 5: Commit assets**

```bash
git add templates/daisyui.min.css templates/alpine.min.js
git commit -m "feat: add DaisyUI v4 and Alpine.js as inlined dashboard assets"
```

---

## Chunk 2: Test Scaffolding

### Task 2: Create test fixtures and skeleton files

**Files:**
- Create: `tests/test_dashboard_data.py`
- Create: `dashboard_data.py` (skeleton only)

- [ ] **Step 1: Create `dashboard_data.py` skeleton with all function stubs**

```python
# dashboard_data.py
import pandas as pd
from datetime import date


def build_context(df: pd.DataFrame, accounts: dict, goals: dict, today=None) -> dict:
    raise NotImplementedError


def compute_kpis(df, accounts: dict, goals: dict, today=None) -> dict:
    raise NotImplementedError


def compute_category_trends(df, months=3, today=None) -> list:
    raise NotImplementedError


def compute_health_score(kpis, category_trends, goals: dict, today=None) -> dict:
    raise NotImplementedError


def compute_actionable_cuts(df, category_trends) -> list:
    raise NotImplementedError


def compute_action_plan(cuts, goals: dict, kpis, today=None) -> list:
    raise NotImplementedError


def compute_spending_pct_of_income(df, income: float, today=None) -> list:
    raise NotImplementedError


def compute_account_balances(accounts: dict) -> list:
    raise NotImplementedError


def compute_top_merchants(df, month: str) -> list:
    raise NotImplementedError


def _score_to_grade(score: int) -> str:
    raise NotImplementedError


def _get_at_risk_goals(goals: dict, today=None) -> list:
    raise NotImplementedError


def _category_icon(category: str) -> str:
    raise NotImplementedError
```

- [ ] **Step 2: Create `tests/test_dashboard_data.py` with shared fixtures**

```python
# tests/test_dashboard_data.py
import pytest
import pandas as pd
from datetime import date
from dashboard_data import (
    compute_kpis, compute_category_trends, compute_health_score,
    compute_actionable_cuts, compute_action_plan,
    compute_spending_pct_of_income, compute_account_balances,
    compute_top_merchants, build_context, _score_to_grade,
)

TODAY = date(2026, 3, 15)  # fixed date for all tests


@pytest.fixture
def sample_df():
    """3 months of synthetic transactions: Jan, Feb, Mar 2026."""
    rows = [
        # March — current month
        {"date": "2026-03-01", "amount": -400.0, "merchant": "Whole Foods",    "category": "Food & Dining",  "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-03-03", "amount": -100.0, "merchant": "Chipotle",       "category": "Food & Dining",  "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-03-05", "amount": -200.0, "merchant": "Uber",           "category": "Transport",      "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-03-10", "amount": -22.99, "merchant": "Netflix",        "category": "Subscriptions",  "account": "Amex",           "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-03-10", "amount": -54.99, "merchant": "Adobe",          "category": "Subscriptions",  "account": "Amex",           "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-03-15", "amount": 5000.0, "merchant": "ACME Payroll",   "category": "Income",         "account": "Chase-Checking", "source": "csv", "is_income": True,  "is_savings": False, "notes": ""},
        # February
        {"date": "2026-02-01", "amount": -300.0, "merchant": "Whole Foods",    "category": "Food & Dining",  "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-02-05", "amount": -180.0, "merchant": "Uber",           "category": "Transport",      "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-02-10", "amount": -22.99, "merchant": "Netflix",        "category": "Subscriptions",  "account": "Amex",           "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-02-15", "amount": 5000.0, "merchant": "ACME Payroll",   "category": "Income",         "account": "Chase-Checking", "source": "csv", "is_income": True,  "is_savings": False, "notes": ""},
        # January
        {"date": "2026-01-01", "amount": -250.0, "merchant": "Whole Foods",    "category": "Food & Dining",  "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-01-05", "amount": -160.0, "merchant": "Uber",           "category": "Transport",      "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-01-10", "amount": -22.99, "merchant": "Netflix",        "category": "Subscriptions",  "account": "Amex",           "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-01-15", "amount": 5000.0, "merchant": "ACME Payroll",   "category": "Income",         "account": "Chase-Checking", "source": "csv", "is_income": True,  "is_savings": False, "notes": ""},
    ]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.fixture
def sample_accounts():
    return {
        "accounts": [
            {"name": "Chase-Checking", "type": "checking",   "institution": "Chase",     "balance": 14200.0, "currency": "USD", "last_updated": "2026-03-15"},
            {"name": "Robinhood",      "type": "investment", "institution": "Robinhood", "balance": 22500.0, "currency": "USD", "last_updated": "2026-03-15"},
        ]
    }


@pytest.fixture
def sample_goals():
    return {
        "monthly_target": 1500.0,
        "goals": [
            {
                "name": "Emergency Fund",
                "target_amount": 10000.0,
                "current_amount": 6200.0,
                "deadline": "2026-12",
                "created": "2026-01-01",
            }
        ],
        "monthly_streak": {
            "current": 3,
            "best": 7,
            "history": {"2026-01": True, "2026-02": True, "2026-03": True},
        },
    }
```

- [ ] **Step 3: Verify the skeleton raises NotImplementedError (sanity check)**

```bash
pytest tests/test_dashboard_data.py --collect-only
```

Expected: 0 errors during collection (no tests yet, just fixtures).

- [ ] **Step 4: Commit skeleton**

```bash
git add dashboard_data.py tests/test_dashboard_data.py
git commit -m "feat: add dashboard_data skeleton and test fixtures"
```

---

## Chunk 3: TDD — compute_kpis

### Task 3: Implement compute_kpis

**Files:**
- Modify: `tests/test_dashboard_data.py` (add TestComputeKPIs class)
- Modify: `dashboard_data.py` (implement compute_kpis)

- [ ] **Step 1: Write the failing tests — add after the fixtures in test file**

```python
class TestComputeKPIs:
    def test_savings_rate_calculated_correctly(self, sample_df, sample_accounts, sample_goals):
        # March income=5000, expenses=400+100+200+22.99+54.99=777.98, saved=4222.02
        kpis = compute_kpis(sample_df, sample_accounts, sample_goals, today=TODAY)
        assert kpis["income"] == pytest.approx(5000.0)
        assert kpis["expenses"] == pytest.approx(777.98)
        assert kpis["saved"] == pytest.approx(4222.02)
        assert kpis["savings_rate"] == pytest.approx(4222.02 / 5000.0)

    def test_zero_income_returns_zero_savings_rate(self, sample_accounts, sample_goals):
        df = pd.DataFrame([{
            "date": pd.Timestamp("2026-03-01"), "amount": -100.0, "merchant": "Test",
            "category": "Other", "account": "Chase", "source": "manual",
            "is_income": False, "is_savings": False, "notes": "",
        }])
        kpis = compute_kpis(df, sample_accounts, sample_goals, today=TODAY)
        assert kpis["savings_rate"] == 0.0
        assert kpis["income"] == 0.0

    def test_monthly_target_comes_from_goals(self, sample_df, sample_accounts, sample_goals):
        kpis = compute_kpis(sample_df, sample_accounts, sample_goals, today=TODAY)
        assert kpis["monthly_target"] == 1500.0

    def test_net_worth_sums_all_accounts(self, sample_df, sample_accounts, sample_goals):
        kpis = compute_kpis(sample_df, sample_accounts, sample_goals, today=TODAY)
        assert kpis["net_worth"] == pytest.approx(36700.0)  # 14200 + 22500

    def test_this_month_format(self, sample_df, sample_accounts, sample_goals):
        kpis = compute_kpis(sample_df, sample_accounts, sample_goals, today=TODAY)
        assert kpis["this_month"] == "2026-03"
```

- [ ] **Step 2: Run tests — confirm they all fail**

```bash
pytest tests/test_dashboard_data.py::TestComputeKPIs -v
```

Expected: 5 FAILED with `NotImplementedError`.

- [ ] **Step 3: Implement compute_kpis in dashboard_data.py**

```python
def compute_kpis(df, accounts: dict, goals: dict, today=None) -> dict:
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
        "savings_rate":   round(saved / income, 4) if income > 0 else 0.0,
        "this_month":     this_month,
    }
```

- [ ] **Step 4: Run tests — confirm all pass**

```bash
pytest tests/test_dashboard_data.py::TestComputeKPIs -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add dashboard_data.py tests/test_dashboard_data.py
git commit -m "feat(tdd): implement compute_kpis"
```

---

## Chunk 4: TDD — compute_category_trends

### Task 4: Implement compute_category_trends

**Files:**
- Modify: `tests/test_dashboard_data.py`
- Modify: `dashboard_data.py`

- [ ] **Step 1: Write failing tests**

```python
class TestCategoryTrends:
    def test_pct_change_direction_up(self, sample_df):
        # Food: Jan $250, Feb $300, Mar $500 — up vs Feb
        trends = compute_category_trends(sample_df, months=3, today=TODAY)
        food = next(t for t in trends if t["name"] == "Food & Dining")
        assert food["direction"] == "up"
        assert food["pct_change"] > 0.05

    def test_pct_change_direction_down(self, sample_df):
        # Transport: Jan $160, Feb $180, Mar $200 — up, not down.
        # Create a df where Transport goes down in Mar
        rows = [
            {"date": "2026-03-01", "amount": -100.0, "merchant": "Uber", "category": "Transport", "account": "Chase", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
            {"date": "2026-02-01", "amount": -300.0, "merchant": "Uber", "category": "Transport", "account": "Chase", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
            {"date": "2026-01-01", "amount": -280.0, "merchant": "Uber", "category": "Transport", "account": "Chase", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        ]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        trends = compute_category_trends(df, months=3, today=TODAY)
        t = next(t for t in trends if t["name"] == "Transport")
        assert t["direction"] == "down"
        assert t["pct_change"] < -0.05

    def test_handles_missing_prior_months(self):
        # Category only exists in current month
        rows = [
            {"date": "2026-03-01", "amount": -200.0, "merchant": "Gym", "category": "Health", "account": "Chase", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        ]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        trends = compute_category_trends(df, months=3, today=TODAY)
        health = next(t for t in trends if t["name"] == "Health")
        assert health["current_amount"] == pytest.approx(200.0)
        assert health["pct_change"] == 0.0  # no prior month = 0% change

    def test_three_month_amounts_returned(self, sample_df):
        trends = compute_category_trends(sample_df, months=3, today=TODAY)
        food = next(t for t in trends if t["name"] == "Food & Dining")
        # prior_amounts has 2 entries (Jan, Feb) when months=3
        assert len(food["prior_amounts"]) == 2

    def test_only_expenses_included(self, sample_df):
        # Income category should not appear in trends
        trends = compute_category_trends(sample_df, months=3, today=TODAY)
        names = [t["name"] for t in trends]
        assert "Income" not in names
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_dashboard_data.py::TestCategoryTrends -v
```

Expected: 5 FAILED with `NotImplementedError`.

- [ ] **Step 3: Implement compute_category_trends**

```python
def compute_category_trends(df, months=3, today=None) -> list:
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
```

- [ ] **Step 4: Run tests — confirm all pass**

```bash
pytest tests/test_dashboard_data.py::TestCategoryTrends -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add dashboard_data.py tests/test_dashboard_data.py
git commit -m "feat(tdd): implement compute_category_trends"
```

---

## Chunk 5: TDD — compute_health_score

### Task 5: Implement health score helpers + compute_health_score

**Files:**
- Modify: `tests/test_dashboard_data.py`
- Modify: `dashboard_data.py`

- [ ] **Step 1: Write failing tests**

```python
class TestScoreToGrade:
    def test_grade_A_at_90(self):    assert _score_to_grade(90)  == "A"
    def test_grade_A_at_100(self):   assert _score_to_grade(100) == "A"
    def test_grade_Bplus_at_80(self): assert _score_to_grade(80) == "B+"
    def test_grade_Bplus_at_89(self): assert _score_to_grade(89) == "B+"
    def test_grade_B_at_75(self):    assert _score_to_grade(75)  == "B"
    def test_grade_B_at_79(self):    assert _score_to_grade(79)  == "B"
    def test_grade_C_at_60(self):    assert _score_to_grade(60)  == "C"
    def test_grade_C_at_74(self):    assert _score_to_grade(74)  == "C"
    def test_grade_D_at_45(self):    assert _score_to_grade(45)  == "D"
    def test_grade_D_at_59(self):    assert _score_to_grade(59)  == "D"
    def test_grade_F_at_44(self):    assert _score_to_grade(44)  == "F"
    def test_grade_F_at_0(self):     assert _score_to_grade(0)   == "F"


class TestHealthScore:
    def _make_kpis(self, savings_rate=0.25, income=5000.0):
        return {
            "income": income, "expenses": income * (1 - savings_rate),
            "saved": income * savings_rate, "savings_rate": savings_rate,
            "net_worth": 40000.0, "monthly_target": 1500.0, "this_month": "2026-03",
        }

    def test_savings_rate_zero_yields_zero_savings_pts(self, sample_goals):
        kpis = self._make_kpis(savings_rate=0.0)
        result = compute_health_score(kpis, [], sample_goals, today=TODAY)
        # savings_rate=0 → 0 pts; no trends → 25 pts; goals all on-track → check
        # Emergency Fund: created 2026-01, deadline 2026-12 = 11 months total,
        #   elapsed ~2 months, expected_pct≈18%, actual=62% → on track → +25 pts
        # No subscriptions → +10 pts; emergency fund >50% → +10 pts
        # Total = 0 + 25 + 25 + 10 + 10 = 70
        assert result["score"] == 70

    def test_savings_rate_10pct_yields_15_savings_pts(self, sample_goals):
        kpis = self._make_kpis(savings_rate=0.10)
        result = compute_health_score(kpis, [], sample_goals, today=TODAY)
        # savings pts = min(0.10/0.20, 1.0) * 30 = 15
        # 15 + 25 + 25 + 10 + 10 = 85 → "B+"
        assert result["score"] == 85
        assert result["grade"] == "B+"

    def test_savings_rate_at_20pct_yields_full_30_pts(self, sample_goals):
        kpis = self._make_kpis(savings_rate=0.20)
        result = compute_health_score(kpis, [], sample_goals, today=TODAY)
        # 30 + 25 + 25 + 10 + 10 = 100
        assert result["score"] == 100
        assert result["grade"] == "A"

    def test_high_spending_trend_deducts_points(self, sample_goals):
        kpis = self._make_kpis(savings_rate=0.20)
        trends = [{"name": "Food & Dining", "pct_change": 0.40, "direction": "up", "current_amount": 1400.0, "prior_amounts": [1000.0, 1000.0]}]
        result = compute_health_score(kpis, trends, sample_goals, today=TODAY)
        # trend pts = max(0, 25 - 1*8) = 17
        # 30 + 17 + 25 + 10 + 10 = 92
        assert result["score"] == 92

    def test_failing_areas_listed(self, sample_goals):
        kpis = self._make_kpis(savings_rate=0.0)
        result = compute_health_score(kpis, [], sample_goals, today=TODAY)
        assert "Savings rate" in result["failing"]

    def test_passing_areas_listed(self, sample_goals):
        kpis = self._make_kpis(savings_rate=0.25)
        result = compute_health_score(kpis, [], sample_goals, today=TODAY)
        assert "Savings rate" in result["passing"]
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_dashboard_data.py::TestScoreToGrade tests/test_dashboard_data.py::TestHealthScore -v
```

Expected: all FAILED with `NotImplementedError`.

- [ ] **Step 3: Implement `_score_to_grade`, `_get_at_risk_goals`, and `compute_health_score`**

```python
def _score_to_grade(score: int) -> str:
    if score >= 90: return "A"
    if score >= 80: return "B+"
    if score >= 75: return "B"
    if score >= 60: return "C"
    if score >= 45: return "D"
    return "F"


def _get_at_risk_goals(goals: dict, today=None) -> list:
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


def compute_health_score(kpis, category_trends, goals: dict, today=None) -> dict:
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
```

- [ ] **Step 4: Run tests — confirm all pass**

```bash
pytest tests/test_dashboard_data.py::TestScoreToGrade tests/test_dashboard_data.py::TestHealthScore -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add dashboard_data.py tests/test_dashboard_data.py
git commit -m "feat(tdd): implement health score algorithm and grade scale"
```

---

## Chunk 6: TDD — compute_actionable_cuts

### Task 6: Implement compute_actionable_cuts

**Files:**
- Modify: `tests/test_dashboard_data.py`
- Modify: `dashboard_data.py`

- [ ] **Step 1: Write failing tests**

```python
class TestActionableCuts:
    def _make_trend(self, name, current, prior1, prior2):
        prior = prior2  # compare current vs immediately prior month
        pct = round((current - prior) / prior, 4) if prior > 0 else 0.0
        direction = "up" if pct > 0.05 else ("down" if pct < -0.05 else "flat")
        return {"name": name, "current_amount": current, "prior_amounts": [prior1, prior2], "pct_change": pct, "direction": direction}

    def test_category_flagged_when_above_15pct(self, sample_df):
        # Food: Jan $250, Feb $300, Mar $500 — Mar/Feb = +67%
        trends = compute_category_trends(sample_df, months=3, today=TODAY)
        cuts = compute_actionable_cuts(sample_df, trends)
        names = [c["category"] for c in cuts]
        assert "Food & Dining" in names

    def test_category_not_flagged_below_threshold(self, sample_df):
        # Create trend where category is flat
        trends = [self._make_trend("Shopping", 100.0, 98.0, 99.0)]
        # Build a df with those shopping transactions in current month
        rows = [{"date": "2026-03-01", "amount": -100.0, "merchant": "Amazon", "category": "Shopping", "account": "Chase", "source": "csv", "is_income": False, "is_savings": False, "notes": ""}]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        cuts = compute_actionable_cuts(df, trends)
        names = [c["category"] for c in cuts]
        assert "Shopping" not in names

    def test_subscriptions_listed_individually(self, sample_df):
        # sample_df has Netflix $22.99 + Adobe $54.99 in March — both ≥$15
        trends = compute_category_trends(sample_df, months=3, today=TODAY)
        cuts = compute_actionable_cuts(sample_df, trends)
        sub_cut = next((c for c in cuts if c["category"] == "Subscriptions"), None)
        assert sub_cut is not None
        # Both Netflix and Adobe should appear in description
        assert "Netflix" in sub_cut["description"] or "Adobe" in sub_cut["description"]

    def test_cuts_sorted_by_saving_desc(self, sample_df):
        trends = compute_category_trends(sample_df, months=3, today=TODAY)
        cuts = compute_actionable_cuts(sample_df, trends)
        savings = [c["potential_saving"] for c in cuts]
        assert savings == sorted(savings, reverse=True)

    def test_empty_df_returns_empty(self):
        cuts = compute_actionable_cuts(pd.DataFrame(), [])
        assert cuts == []
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_dashboard_data.py::TestActionableCuts -v
```

Expected: all FAILED.

- [ ] **Step 3: Implement `_category_icon` and `compute_actionable_cuts`**

```python
def _category_icon(category: str) -> str:
    return {
        "Food & Dining": "🍔",
        "Transport":     "🚗",
        "Shopping":      "🛍️",
        "Health":        "💊",
        "Entertainment": "🎬",
        "Subscriptions": "📺",
    }.get(category, "💸")


def compute_actionable_cuts(df, category_trends) -> list:
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
```

- [ ] **Step 4: Run tests — confirm all pass**

```bash
pytest tests/test_dashboard_data.py::TestActionableCuts -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add dashboard_data.py tests/test_dashboard_data.py
git commit -m "feat(tdd): implement compute_actionable_cuts"
```

---

## Chunk 7: TDD — compute_action_plan

### Task 7: Implement compute_action_plan

**Files:**
- Modify: `tests/test_dashboard_data.py`
- Modify: `dashboard_data.py`

- [ ] **Step 1: Write failing tests**

```python
class TestActionPlan:
    def _make_cuts(self, n):
        return [
            {"category": f"Cat{i}", "description": f"Cut {i}", "detail": "", "potential_saving": float(100 - i * 10), "icon": "💸"}
            for i in range(n)
        ]

    def test_returns_up_to_three_steps(self, sample_goals):
        cuts = self._make_cuts(5)
        plan = compute_action_plan(cuts, sample_goals, {}, today=TODAY)
        assert len(plan) == 3

    def test_returns_fewer_steps_when_fewer_cuts(self, sample_goals):
        cuts = self._make_cuts(2)
        plan = compute_action_plan(cuts, sample_goals, {}, today=TODAY)
        assert len(plan) == 2

    def test_returns_empty_when_no_cuts(self, sample_goals):
        plan = compute_action_plan([], sample_goals, {}, today=TODAY)
        assert plan == []

    def test_month_labels_sequential_format_month_yyyy(self, sample_goals):
        cuts = self._make_cuts(3)
        plan = compute_action_plan(cuts, sample_goals, {}, today=TODAY)
        assert plan[0]["month_label"] == "March 2026"
        assert plan[1]["month_label"] == "April 2026"
        assert plan[2]["month_label"] == "May 2026"

    def test_step_numbers_are_1_2_3(self, sample_goals):
        cuts = self._make_cuts(3)
        plan = compute_action_plan(cuts, sample_goals, {}, today=TODAY)
        assert [s["step"] for s in plan] == [1, 2, 3]

    def test_step_links_to_at_risk_goal(self):
        # Goal created 2026-01, deadline 2026-03, current=1000, target=10000
        # elapsed=2mo, total=2mo → expected_pct=100%, actual=10% → at-risk
        goals = {
            "monthly_target": 500.0,
            "goals": [{"name": "Japan Trip", "target_amount": 10000.0, "current_amount": 1000.0, "deadline": "2026-03", "created": "2026-01-01"}],
            "monthly_streak": {},
        }
        cuts = [{"category": "Food", "description": "Food high", "detail": "", "potential_saving": 300.0, "icon": "🍔"}]
        plan = compute_action_plan(cuts, goals, {}, today=TODAY)
        assert plan[0]["goal_link"] == "Japan Trip"
        assert "Japan Trip" in plan[0]["description"]
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_dashboard_data.py::TestActionPlan -v
```

Expected: all FAILED.

- [ ] **Step 3: Implement compute_action_plan**

```python
def compute_action_plan(cuts, goals: dict, kpis, today=None) -> list:
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
```

- [ ] **Step 4: Run tests — confirm all pass**

```bash
pytest tests/test_dashboard_data.py::TestActionPlan -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add dashboard_data.py tests/test_dashboard_data.py
git commit -m "feat(tdd): implement compute_action_plan"
```

---

## Chunk 8: TDD — Remaining helper functions

### Task 8: Implement spending_pct, account_balances, top_merchants

**Files:**
- Modify: `tests/test_dashboard_data.py`
- Modify: `dashboard_data.py`

- [ ] **Step 1: Write failing tests**

```python
class TestSpendingPctOfIncome:
    def test_pct_calculated_correctly(self, sample_df):
        # March expenses: Food $500, Transport $200, Subs $77.98 — income $5000
        pct = compute_spending_pct_of_income(sample_df, income=5000.0, today=TODAY)
        food = next(p for p in pct if p["name"] == "Food & Dining")
        assert food["amount"] == pytest.approx(500.0)
        assert food["pct_of_income"] == pytest.approx(10.0)  # 500/5000*100

    def test_zero_income_returns_empty(self, sample_df):
        pct = compute_spending_pct_of_income(sample_df, income=0.0, today=TODAY)
        assert pct == []

    def test_sorted_by_amount_desc(self, sample_df):
        pct = compute_spending_pct_of_income(sample_df, income=5000.0, today=TODAY)
        amounts = [p["amount"] for p in pct]
        assert amounts == sorted(amounts, reverse=True)


class TestAccountBalances:
    def test_share_of_total_calculated_correctly(self, sample_accounts):
        balances = compute_account_balances(sample_accounts)
        chase = next(b for b in balances if b["name"] == "Chase-Checking")
        # 14200 / (14200 + 22500) = 0.3869
        assert chase["share_of_total"] == pytest.approx(14200 / 36700, rel=0.01)

    def test_negative_balance_excluded_from_share_denominator(self):
        accounts = {"accounts": [
            {"name": "Chase",  "type": "checking",  "institution": "Chase",  "balance":  5000.0, "currency": "USD", "last_updated": "2026-03-01"},
            {"name": "Amex",   "type": "credit",    "institution": "Amex",   "balance": -1000.0, "currency": "USD", "last_updated": "2026-03-01"},
        ]}
        balances = compute_account_balances(accounts)
        chase = next(b for b in balances if b["name"] == "Chase")
        assert chase["share_of_total"] == pytest.approx(1.0)  # only positive balance counts

    def test_all_accounts_returned(self, sample_accounts):
        balances = compute_account_balances(sample_accounts)
        assert len(balances) == 2


class TestTopMerchants:
    def test_filters_to_given_month(self, sample_df):
        merchants = compute_top_merchants(sample_df, "2026-03")
        names = [m["name"] for m in merchants]
        # Uber and Whole Foods are in March
        assert "Whole Foods" in names
        # ACME Payroll is income (positive amount) — should not appear
        assert "ACME Payroll" not in names

    def test_returns_top_10_by_spend(self):
        # Create 12 merchants with varying spend in same month
        rows = [
            {"date": "2026-03-01", "amount": float(-(i + 1) * 10), "merchant": f"Store{i:02d}",
             "category": "Shopping", "account": "Chase", "source": "csv",
             "is_income": False, "is_savings": False, "notes": ""}
            for i in range(12)
        ]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        merchants = compute_top_merchants(df, "2026-03")
        assert len(merchants) == 10

    def test_includes_tx_count(self, sample_df):
        # Whole Foods has 1 tx in March, Chipotle has 1 tx
        merchants = compute_top_merchants(sample_df, "2026-03")
        wf = next(m for m in merchants if m["name"] == "Whole Foods")
        assert wf["tx_count"] == 1
        assert wf["amount"] == pytest.approx(400.0)
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_dashboard_data.py::TestSpendingPctOfIncome tests/test_dashboard_data.py::TestAccountBalances tests/test_dashboard_data.py::TestTopMerchants -v
```

Expected: all FAILED.

- [ ] **Step 3: Implement the three functions**

```python
def compute_spending_pct_of_income(df, income: float, today=None) -> list:
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


def compute_top_merchants(df, month: str) -> list:
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
```

- [ ] **Step 4: Run tests — confirm all pass**

```bash
pytest tests/test_dashboard_data.py::TestSpendingPctOfIncome tests/test_dashboard_data.py::TestAccountBalances tests/test_dashboard_data.py::TestTopMerchants -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add dashboard_data.py tests/test_dashboard_data.py
git commit -m "feat(tdd): implement spending_pct_of_income, account_balances, top_merchants"
```

---

## Chunk 9: TDD — build_context integration

### Task 9: Implement build_context

**Files:**
- Modify: `tests/test_dashboard_data.py`
- Modify: `dashboard_data.py`

- [ ] **Step 1: Write failing tests**

```python
class TestBuildContext:
    def test_context_has_all_required_keys(self, sample_df, sample_accounts, sample_goals):
        ctx = build_context(sample_df, sample_accounts, sample_goals, today=TODAY)
        required = [
            "kpis", "category_trends", "health", "cuts", "action_plan",
            "spending_pct", "account_balances", "top_merchants",
            "trend_labels", "trend_values", "goals_display",
            "monthly_streak", "monthly_target", "generated_at",
        ]
        for key in required:
            assert key in ctx, f"Missing key: {key}"

    def test_trend_labels_has_12_entries(self, sample_df, sample_accounts, sample_goals):
        ctx = build_context(sample_df, sample_accounts, sample_goals, today=TODAY)
        assert len(ctx["trend_labels"]) == 12
        assert len(ctx["trend_values"]) == 12

    def test_goals_display_contains_pct(self, sample_df, sample_accounts, sample_goals):
        ctx = build_context(sample_df, sample_accounts, sample_goals, today=TODAY)
        assert len(ctx["goals_display"]) == 1
        g = ctx["goals_display"][0]
        assert g["name"] == "Emergency Fund"
        assert g["pct"] == 62  # 6200/10000*100

    def test_empty_df_returns_zero_kpis(self, sample_accounts, sample_goals):
        ctx = build_context(pd.DataFrame(), sample_accounts, sample_goals, today=TODAY)
        assert ctx["kpis"]["income"] == 0.0
        assert ctx["kpis"]["net_worth"] == pytest.approx(36700.0)
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_dashboard_data.py::TestBuildContext -v
```

Expected: all FAILED.

- [ ] **Step 3: Implement build_context**

```python
def build_context(df: pd.DataFrame, accounts: dict, goals: dict, today=None) -> dict:
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
        "generated_at":     today.strftime("%Y-%m-%d"),
    }
```

- [ ] **Step 4: Run the full test suite — all dashboard_data tests must pass**

```bash
pytest tests/test_dashboard_data.py -v
```

Expected: all PASSED, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add dashboard_data.py tests/test_dashboard_data.py
git commit -m "feat(tdd): implement build_context — dashboard data layer complete"
```

---

## Chunk 10: Refactor dashboard.py

### Task 10: Replace dashboard.py with thin renderer

**Files:**
- Modify: `dashboard.py`

- [ ] **Step 1: Replace the full contents of dashboard.py**

```python
# dashboard.py
import json
import os
import pandas as pd
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from dashboard_data import build_context

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


def _load_files(data_dir: str):
    store_path    = f"{data_dir}/transactions.csv"
    accounts_path = f"{data_dir}/accounts.json"
    goals_path    = f"{data_dir}/goals.json"

    try:
        df = pd.read_csv(store_path)
        df["date"] = pd.to_datetime(df["date"])
    except FileNotFoundError:
        df = pd.DataFrame()

    accounts = {"accounts": []}
    if os.path.exists(accounts_path):
        with open(accounts_path) as f:
            accounts = json.load(f)

    goals = {"monthly_target": 0.0, "goals": [], "monthly_streak": {}}
    if os.path.exists(goals_path):
        with open(goals_path) as f:
            goals = json.load(f)

    return df, accounts, goals


def build_dashboard(data_dir: str = "data", output_path: str = "reports/dashboard.html") -> str:
    df, accounts, goals = _load_files(data_dir)
    context = build_context(df, accounts, goals)

    env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR))
    env.filters["format_currency"] = lambda v: f"{v:,.2f}"
    template = env.get_template("dashboard.html.j2")

    def _read(filename):
        with open(os.path.join(_TEMPLATES_DIR, filename)) as f:
            return f.read()

    html = template.render(
        **context,
        chartjs=_read("chart.min.js"),
        daisyui_css=_read("daisyui.min.css"),
        alpine_js=_read("alpine.min.js"),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    return output_path
```

- [ ] **Step 2: Run existing integration tests — must still pass**

```bash
pytest tests/test_dashboard.py -v
```

Expected: tests fail only because the template doesn't exist yet — that's expected. If they fail for Python import errors, fix those first before continuing.

- [ ] **Step 3: Commit**

```bash
git add dashboard.py
git commit -m "refactor: slim dashboard.py to thin renderer using build_context"
```

---

## Chunk 11: Rewrite the Jinja2 Template

### Task 11: Write the full 4-tab dashboard template

**Files:**
- Rewrite: `templates/dashboard.html.j2`

> **Note:** This is a single large Write operation. The template provides the complete HTML for all 4 tabs. Copy it exactly — Jinja2 syntax uses `{{ }}` for values and `{% %}` for control flow.

- [ ] **Step 1: Write the full template**

```html
{# templates/dashboard.html.j2 #}
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Finance Dashboard</title>
<style>{{ daisyui_css }}</style>
<script>{{ alpine_js }}</script>
<script>{{ chartjs }}</script>
<style>
  * { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', sans-serif; box-sizing: border-box; }
  body { background: #09090b; color: #fafafa; margin: 0; padding: 0; min-height: 100vh; }

  /* Design tokens */
  :root {
    --bg:       #09090b;
    --surface:  #18181b;
    --surface2: #27272a;
    --border:   #3f3f46;
    --muted:    #71717a;
    --green:    #22c55e;
    --red:      #ef4444;
    --blue:     #3b82f6;
    --purple:   #a855f7;
    --amber:    #f59e0b;
    --cyan:     #06b6d4;
  }

  .card { background: var(--surface); border: 1px solid var(--surface2); border-radius: 12px; padding: 20px; transition: border-color 0.2s; }
  .card:hover { border-color: var(--border); }
  .card-accent-green::before  { content:''; display:block; height:2px; background:linear-gradient(90deg,var(--green),transparent); border-radius:12px 12px 0 0; margin:-20px -20px 16px; }
  .card-accent-red::before    { content:''; display:block; height:2px; background:linear-gradient(90deg,var(--red),transparent);   border-radius:12px 12px 0 0; margin:-20px -20px 16px; }
  .card-accent-blue::before   { content:''; display:block; height:2px; background:linear-gradient(90deg,var(--blue),transparent);  border-radius:12px 12px 0 0; margin:-20px -20px 16px; }
  .card-accent-purple::before { content:''; display:block; height:2px; background:linear-gradient(90deg,var(--purple),transparent);border-radius:12px 12px 0 0; margin:-20px -20px 16px; }

  .kpi-label { font-size:0.68rem; font-weight:600; color:var(--muted); text-transform:uppercase; letter-spacing:0.06em; }
  .kpi-value { font-size:1.65rem; font-weight:700; margin:6px 0 4px; letter-spacing:-0.02em; }
  .kpi-sub   { font-size:0.7rem; color:var(--muted); margin-top:4px; }

  .badge { display:inline-flex; align-items:center; font-size:0.68rem; font-weight:600; padding:2px 8px; border-radius:999px; }
  .badge-up      { background:rgba(239,68,68,0.12);  color:var(--red); }
  .badge-down    { background:rgba(34,197,94,0.12);  color:var(--green); }
  .badge-neutral { background:rgba(113,113,122,0.15); color:var(--muted); }
  .badge-blue    { background:rgba(59,130,246,0.12); color:var(--blue); }

  .tab-bar { display:flex; gap:2px; padding:4px; background:var(--surface); border:1px solid var(--surface2); border-radius:10px; width:fit-content; }
  .tab-btn { padding:7px 18px; border-radius:7px; font-size:0.8rem; font-weight:500; color:var(--muted); cursor:pointer; border:none; background:transparent; transition:all 0.15s; }
  .tab-btn:hover  { color:#fafafa; background:var(--surface2); }
  .tab-btn.active { background:var(--surface2); color:#fafafa; font-weight:600; }

  .section-label { font-size:0.68rem; font-weight:600; color:var(--muted); text-transform:uppercase; letter-spacing:0.07em; margin-bottom:12px; }

  .grid-4 { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }
  .grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:12px; }

  .bar-track { flex:1; background:var(--surface2); border-radius:4px; height:7px; overflow:hidden; }
  .bar-fill  { height:7px; border-radius:4px; }

  .progress-track { background:var(--surface2); border-radius:6px; height:6px; }
  .progress-fill  { height:6px; border-radius:6px; background:linear-gradient(90deg,var(--blue),var(--cyan)); }

  .insight-card { display:flex; gap:12px; align-items:flex-start; padding:14px 16px; background:var(--surface); border:1px solid var(--surface2); border-radius:10px; }
  .insight-icon { width:32px; height:32px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:0.9rem; flex-shrink:0; }

  .data-table { width:100%; border-collapse:collapse; font-size:0.8rem; }
  .data-table th { font-size:0.68rem; font-weight:600; color:var(--muted); text-transform:uppercase; letter-spacing:0.05em; padding:0 0 10px; text-align:left; border-bottom:1px solid var(--surface2); }
  .data-table th:last-child { text-align:right; }
  .data-table td { padding:9px 0; border-bottom:1px solid var(--surface2); color:#e4e4e7; vertical-align:middle; }
  .data-table tr:last-child td { border-bottom:none; }
  .data-table td:last-child { text-align:right; font-weight:600; color:var(--red); }

  .spark { display:flex; align-items:flex-end; gap:2px; height:22px; width:50px; }
  .spark-bar { flex:1; border-radius:2px 2px 0 0; min-width:6px; }

  .cat-badge { display:inline-block; font-size:0.68rem; font-weight:500; padding:2px 8px; border-radius:4px; }

  [x-cloak] { display:none !important; }
</style>
</head>
<body x-data="{ tab: 'overview' }">

<div style="max-width:1100px;margin:0 auto;padding:28px 24px">

  {# ── Header ── #}
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px">
    <div>
      <div style="font-size:1.2rem;font-weight:700;letter-spacing:-0.01em">Finance Dashboard</div>
      <div style="font-size:0.72rem;color:var(--muted);margin-top:2px">Last updated: {{ generated_at }}</div>
    </div>
    <div style="display:flex;gap:8px;align-items:center">
      <div style="font-size:0.75rem;background:var(--surface);border:1px solid var(--surface2);padding:5px 12px;border-radius:7px;color:var(--muted)">
        {{ kpis.this_month }}
      </div>
    </div>
  </div>

  {# ── Tab Bar ── #}
  <div class="tab-bar" style="margin-bottom:24px">
    <button class="tab-btn" :class="tab==='overview'  ? 'active' : ''" @click="tab='overview'">Overview</button>
    <button class="tab-btn" :class="tab==='spending'  ? 'active' : ''" @click="tab='spending'">Spending</button>
    <button class="tab-btn" :class="tab==='goals'     ? 'active' : ''" @click="tab='goals'">Goals</button>
    <button class="tab-btn" :class="tab==='insights'  ? 'active' : ''" @click="tab='insights'">Insights</button>
  </div>

  {# ════════════════════════════════════════════
     OVERVIEW TAB
  ════════════════════════════════════════════ #}
  <div x-show="tab==='overview'">

    {# KPI Row #}
    <div class="grid-4" style="margin-bottom:16px">
      <div class="card card-accent-green">
        <div class="kpi-label">Net Worth</div>
        <div class="kpi-value" style="color:var(--green)">${{ kpis.net_worth | format_currency }}</div>
        <div class="kpi-sub">All accounts combined</div>
      </div>
      <div class="card">
        <div class="kpi-label">Income</div>
        <div class="kpi-value">${{ kpis.income | format_currency }}</div>
        <div class="kpi-sub">{{ kpis.this_month }}</div>
      </div>
      <div class="card card-accent-red">
        <div class="kpi-label">Expenses</div>
        <div class="kpi-value" style="color:var(--red)">${{ kpis.expenses | format_currency }}</div>
        <div class="kpi-sub">{{ kpis.this_month }}</div>
      </div>
      <div class="card card-accent-blue">
        <div class="kpi-label">Saved</div>
        <div class="kpi-value" style="color:var(--blue)">${{ kpis.saved | format_currency }}</div>
        {% if kpis.monthly_target > 0 %}
        <div class="kpi-sub">
          <span class="badge {% if kpis.saved >= kpis.monthly_target %}badge-down{% else %}badge-up{% endif %}">
            {% if kpis.saved >= kpis.monthly_target %}✓ Goal hit{% else %}${{ (kpis.monthly_target - kpis.saved) | format_currency }} behind{% endif %}
          </span>
        </div>
        {% endif %}
      </div>
    </div>

    {# Charts row #}
    <div class="grid-2" style="margin-bottom:16px">
      <div class="card">
        <div class="section-label">Monthly Spending — 12 Months</div>
        <canvas id="trendChart" style="max-height:160px"></canvas>
      </div>
      <div class="card">
        <div class="section-label">Account Balances</div>
        {% for a in account_balances %}
        <div style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;margin-bottom:5px">
            <span style="font-size:0.78rem">{{ a.name }}</span>
            <span style="font-size:0.78rem;font-weight:600;color:{% if a.balance >= 0 %}var(--green){% else %}var(--red){% endif %}">
              {% if a.balance < 0 %}-{% endif %}${{ a.balance | abs | format_currency }}
            </span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width:{{ [a.share_of_total * 100, 100] | min }}%"></div>
          </div>
        </div>
        {% else %}
        <div style="font-size:0.8rem;color:var(--muted)">No accounts configured.</div>
        {% endfor %}
      </div>
    </div>

    {# Top Merchants #}
    {% if top_merchants %}
    <div class="card">
      <div class="section-label">Top Merchants — {{ kpis.this_month }}</div>
      <table class="data-table">
        <thead>
          <tr>
            <th style="width:32px">#</th>
            <th>Merchant</th>
            <th>Category</th>
            <th style="text-align:center">Txns</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {% for m in top_merchants %}
          <tr>
            <td style="color:var(--muted)">{{ loop.index }}</td>
            <td style="font-weight:500">{{ m.name }}</td>
            <td>
              <span class="cat-badge" style="background:rgba(59,130,246,0.1);color:var(--blue)">{{ m.category }}</span>
            </td>
            <td style="text-align:center;color:var(--muted)">{{ m.tx_count }}×</td>
            <td>${{ m.amount | format_currency }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% endif %}
  </div>

  {# ════════════════════════════════════════════
     SPENDING TAB
  ════════════════════════════════════════════ #}
  <div x-show="tab==='spending'" x-cloak>

    {# Period selector (UI only — filter logic is Phase 2) #}
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <div style="font-size:0.88rem;font-weight:600">Spending Breakdown</div>
      <div style="display:flex;gap:4px">
        {% for period in ['This Month', '3 Months', '6 Months', 'Year'] %}
        <button style="padding:4px 12px;border-radius:6px;font-size:0.72rem;border:1px solid var(--surface2);cursor:pointer;
          {% if loop.first %}background:var(--surface2);color:#fafafa;font-weight:600;{% else %}background:var(--surface);color:var(--muted);{% endif %}">
          {{ period }}
        </button>
        {% endfor %}
      </div>
    </div>

    {# Row 1: Donut + Waterfall #}
    <div class="grid-2" style="margin-bottom:12px">

      {# Category donut #}
      <div class="card">
        <div class="section-label">Where It Went</div>
        <div style="display:flex;align-items:center;gap:20px">
          <div style="flex-shrink:0;position:relative">
            <canvas id="donutChart" style="width:110px;height:110px"></canvas>
          </div>
          <div style="flex:1">
            {% for item in spending_pct %}
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
              <span style="font-size:0.76rem;color:#a1a1aa">{{ item.name }}</span>
              <span style="font-size:0.76rem;font-weight:600">${{ item.amount | format_currency }}</span>
            </div>
            {% else %}
            <div style="font-size:0.8rem;color:var(--muted)">No expense data.</div>
            {% endfor %}
          </div>
        </div>
      </div>

      {# Income vs Expenses bar #}
      <div class="card">
        <div class="section-label">Income vs Expenses</div>
        <canvas id="incomeChart" style="max-height:140px"></canvas>
        {% if kpis.income > 0 %}
        <div style="margin-top:12px;padding:10px 14px;background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.15);border-radius:8px;font-size:0.72rem;color:var(--blue)">
          Savings rate <strong>{{ "%.1f" | format(kpis.savings_rate * 100) }}%</strong>
          {% if kpis.monthly_target > 0 %} — need <strong>{{ "%.1f" | format(kpis.monthly_target / kpis.income * 100) }}%</strong> to hit goal{% endif %}
        </div>
        {% endif %}
      </div>
    </div>

    {# Row 2: Per-category sparkline trends #}
    {% if category_trends %}
    <div class="card" style="margin-bottom:12px">
      <div class="section-label">Category Trend — Last 3 Months</div>
      {% for trend in category_trends %}
      <div style="display:flex;align-items:center;gap:14px;{% if not loop.last %}margin-bottom:14px{% endif %}">
        <div style="width:120px;font-size:0.78rem;color:#e4e4e7;font-weight:500;flex-shrink:0">{{ trend.name }}</div>
        <div class="spark">
          {% set all_amounts = trend.prior_amounts + [trend.current_amount] %}
          {% set max_amt = all_amounts | max %}
          {% for amt in all_amounts %}
          <div class="spark-bar" style="
            height:{{ [((amt / max_amt * 100) if max_amt > 0 else 0) | int, 4] | max }}%;
            background:{% if loop.last %}{% if trend.direction == 'up' %}var(--red){% elif trend.direction == 'down' %}var(--green){% else %}var(--blue){% endif %}{% else %}var(--surface2){% endif %};
            opacity:{% if loop.last %}1{% else %}0.5{% endif %}">
          </div>
          {% endfor %}
        </div>
        <div style="font-size:0.76rem;font-weight:600;color:#e4e4e7;width:70px;flex-shrink:0">${{ trend.current_amount | format_currency }}</div>
        <span class="badge {% if trend.direction == 'up' %}badge-up{% elif trend.direction == 'down' %}badge-down{% else %}badge-neutral{% endif %}">
          {% if trend.direction == 'up' %}↑{% elif trend.direction == 'down' %}↓{% else %}→{% endif %}
          {{ "%.0f" | format((trend.pct_change * 100) | abs) }}%
        </span>
        {% if trend.prior_amounts %}
        <div style="font-size:0.68rem;color:var(--muted);flex:1">
          {% for amt in trend.prior_amounts %}${{ amt | format_currency }}{% if not loop.last %} → {% endif %}{% endfor %} → ${{ trend.current_amount | format_currency }}
        </div>
        {% endif %}
      </div>
      {% endfor %}
    </div>
    {% endif %}

    {# Row 3: % of income #}
    {% if spending_pct %}
    <div class="card">
      <div class="section-label">Where Did My Money Go — % of Income</div>
      {% for item in spending_pct %}
      <div style="display:flex;align-items:center;gap:10px;{% if not loop.last %}margin-bottom:10px{% endif %}">
        <div style="width:120px;font-size:0.78rem;color:#a1a1aa;flex-shrink:0">{{ item.name }}</div>
        <div class="bar-track"><div class="bar-fill" style="width:{{ [item.pct_of_income, 100] | min }}%;background:var(--blue)"></div></div>
        <div style="width:65px;text-align:right;font-size:0.72rem;font-weight:600;color:var(--blue);flex-shrink:0">{{ item.pct_of_income }}%</div>
      </div>
      {% endfor %}
    </div>
    {% endif %}
  </div>

  {# ════════════════════════════════════════════
     GOALS TAB
  ════════════════════════════════════════════ #}
  <div x-show="tab==='goals'" x-cloak>
    <div class="grid-2" style="margin-bottom:12px">

      {# Monthly streak #}
      <div class="card">
        <div class="section-label">Monthly Savings Streak</div>
        {% set streak = monthly_streak %}
        <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:12px">
          <span style="font-size:2.2rem;font-weight:700;color:var(--amber)">{{ streak.get('current', 0) }}</span>
          <span style="font-size:0.85rem;color:var(--muted)">months in a row · Best: {{ streak.get('best', 0) }}</span>
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          {% for month_key, hit in streak.get('history', {}).items() %}
          <div style="width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:0.65rem;font-weight:600;
            {% if hit %}background:rgba(34,197,94,0.15);border:1px solid rgba(34,197,94,0.3);color:var(--green)
            {% else %}background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:var(--red){% endif %}">
            {{ month_key[-2:] }}
          </div>
          {% endfor %}
        </div>
      </div>

      {# Monthly target #}
      <div class="card">
        <div class="section-label">Monthly Target</div>
        {% if monthly_target > 0 %}
        <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px">
          <span style="font-size:1.5rem;font-weight:700;color:var(--blue)">${{ kpis.saved | format_currency }}</span>
          <span style="font-size:0.8rem;color:var(--muted)">of ${{ monthly_target | format_currency }} goal</span>
        </div>
        <div class="progress-track" style="margin-bottom:8px">
          <div class="progress-fill" style="width:{{ [kpis.saved / monthly_target * 100, 100] | min }}%"></div>
        </div>
        <div style="font-size:0.72rem;color:var(--muted)">
          {% if kpis.saved >= monthly_target %}On track ✓{% else %}${{ (monthly_target - kpis.saved) | format_currency }} behind target{% endif %}
        </div>
        {% else %}
        <div style="font-size:0.8rem;color:var(--muted)">No monthly target set. Run: <code>finance goal set monthly --amount 1500</code></div>
        {% endif %}
      </div>
    </div>

    {# Named goals #}
    {% if goals_display %}
    <div class="card">
      <div class="section-label">Named Goals</div>
      {% for g in goals_display %}
      <div style="{% if not loop.last %}margin-bottom:20px{% endif %}">
        <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px">
          <div style="font-size:0.85rem;font-weight:600">{{ g.name }}</div>
          <div style="display:flex;gap:8px;align-items:center">
            <span style="font-size:0.72rem;color:var(--muted)">${{ g.current | format_currency }} / ${{ g.target | format_currency }}</span>
            <span class="badge badge-blue">{{ g.pct }}%</span>
          </div>
        </div>
        <div class="progress-track" style="margin-bottom:6px">
          <div class="progress-fill" style="width:{{ [g.pct, 100] | min }}%"></div>
        </div>
        <div style="font-size:0.7rem;color:var(--muted)">Deadline: {{ g.deadline }}</div>
      </div>
      {% endfor %}
    </div>
    {% else %}
    <div class="card" style="font-size:0.8rem;color:var(--muted)">
      No named goals. Run: <code>finance goal set "Emergency Fund" --target 10000 --by 2026-12</code>
    </div>
    {% endif %}
  </div>

  {# ════════════════════════════════════════════
     INSIGHTS TAB
  ════════════════════════════════════════════ #}
  <div x-show="tab==='insights'" x-cloak>

    {# Health Score #}
    <div class="card" style="display:flex;align-items:center;gap:24px;margin-bottom:12px">
      <div style="position:relative;flex-shrink:0">
        <canvas id="healthChart" style="width:90px;height:90px"></canvas>
        <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center">
          <div style="font-size:1.3rem;font-weight:700;color:{% if health.score >= 80 %}var(--green){% elif health.score >= 60 %}var(--amber){% else %}var(--red){% endif %}">{{ health.grade }}</div>
        </div>
      </div>
      <div style="flex:1">
        <div style="font-size:1rem;font-weight:700;margin-bottom:4px">
          Financial Health Score: <span style="color:{% if health.score >= 80 %}var(--green){% elif health.score >= 60 %}var(--amber){% else %}var(--red){% endif %}">{{ health.score }} / 100</span>
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px">
          {% for area in health.passing %}
          <span style="padding:3px 10px;border-radius:6px;background:rgba(34,197,94,0.1);color:var(--green);font-size:0.68rem;font-weight:600">✓ {{ area }}</span>
          {% endfor %}
          {% for area in health.failing %}
          <span style="padding:3px 10px;border-radius:6px;background:rgba(239,68,68,0.1);color:var(--red);font-size:0.68rem;font-weight:600">✗ {{ area }}</span>
          {% endfor %}
        </div>
      </div>
    </div>

    {# Actionable Cuts #}
    {% if cuts %}
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <div class="section-label" style="margin-bottom:0">Actionable Cuts</div>
      <div style="font-size:0.72rem;color:var(--green);font-weight:600">
        Potential: ${{ cuts | sum(attribute='potential_saving') | format_currency }}/mo
      </div>
    </div>
    <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:16px">
      {% for cut in cuts %}
      <div class="insight-card">
        <div class="insight-icon" style="background:rgba(239,68,68,0.1)">{{ cut.icon }}</div>
        <div style="flex:1">
          <div style="font-size:0.82rem;font-weight:600;margin-bottom:3px">{{ cut.description }}</div>
          <div style="font-size:0.74rem;color:var(--muted)">{{ cut.detail }}</div>
        </div>
        <div style="font-size:0.82rem;font-weight:700;color:var(--green);flex-shrink:0;white-space:nowrap">
          +${{ cut.potential_saving | format_currency }}/mo
        </div>
      </div>
      {% endfor %}
    </div>
    {% endif %}

    {# Action Plan #}
    {% if action_plan %}
    <div class="card">
      <div class="section-label">Your Action Plan</div>
      {% for step in action_plan %}
      <div style="display:flex;gap:12px;align-items:flex-start;{% if not loop.last %}margin-bottom:14px{% endif %}">
        <div style="width:24px;height:24px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:0.65rem;font-weight:700;flex-shrink:0;
          {% if loop.index == 1 %}background:rgba(239,68,68,0.15);border:1px solid var(--red);color:var(--red)
          {% elif loop.index == 2 %}background:rgba(245,158,11,0.15);border:1px solid var(--amber);color:var(--amber)
          {% else %}background:rgba(34,197,94,0.15);border:1px solid var(--green);color:var(--green){% endif %}">
          {{ step.step }}
        </div>
        <div>
          <div style="font-size:0.82rem;font-weight:600;margin-bottom:2px">{{ step.month_label }} — {{ step.action }}</div>
          <div style="font-size:0.74rem;color:var(--muted)">{{ step.description }}</div>
        </div>
      </div>
      {% endfor %}
    </div>
    {% else %}
    <div class="card" style="font-size:0.8rem;color:var(--muted)">
      No actionable cuts found — your spending looks well-controlled.
    </div>
    {% endif %}

  </div>{# end insights #}

  <div style="font-size:0.68rem;color:var(--muted);text-align:right;margin-top:20px">Generated: {{ generated_at }}</div>
</div>{# end container #}

<script>
// Trend bar chart (Overview)
(function() {
  const el = document.getElementById('trendChart');
  if (!el) return;
  new Chart(el, {
    type: 'bar',
    data: {
      labels: {{ trend_labels | tojson }},
      datasets: [{
        data: {{ trend_values | tojson }},
        backgroundColor: {{ trend_labels | tojson }}.map((_, i, arr) =>
          i === arr.length - 1 ? 'rgba(239,68,68,0.8)' : 'rgba(63,63,70,0.6)'
        ),
        borderRadius: 3,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#71717a', font: { size: 10 } }, grid: { color: '#27272a' } },
        y: { ticks: { color: '#71717a', font: { size: 10 }, callback: v => '$' + v.toLocaleString() }, grid: { color: '#27272a' } }
      }
    }
  });
})();

// Category donut (Spending)
(function() {
  const el = document.getElementById('donutChart');
  if (!el) return;
  const labels = {{ spending_pct | map(attribute='name') | list | tojson }};
  const data   = {{ spending_pct | map(attribute='amount') | list | tojson }};
  if (!data.length) return;
  new Chart(el, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data, backgroundColor: ['#ef4444','#3b82f6','#a855f7','#f59e0b','#22c55e','#06b6d4','#ec4899'], borderWidth: 0, hoverOffset: 4 }]
    },
    options: {
      responsive: false, cutout: '70%',
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` $${ctx.parsed.toLocaleString('en-US',{minimumFractionDigits:2})}` } } }
    }
  });
})();

// Income vs Expenses bar (Spending)
(function() {
  const el = document.getElementById('incomeChart');
  if (!el) return;
  new Chart(el, {
    type: 'bar',
    data: {
      labels: ['Income', 'Expenses', 'Saved'],
      datasets: [{
        data: [{{ kpis.income }}, {{ kpis.expenses }}, {{ kpis.saved }}],
        backgroundColor: ['rgba(34,197,94,0.7)', 'rgba(239,68,68,0.7)', 'rgba(59,130,246,0.7)'],
        borderRadius: 5,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#71717a' }, grid: { color: '#27272a' } },
        y: { ticks: { color: '#71717a', callback: v => '$' + v.toLocaleString() }, grid: { color: '#27272a' } }
      }
    }
  });
})();

// Health score ring (Insights)
(function() {
  const el = document.getElementById('healthChart');
  if (!el) return;
  const score = {{ health.score }};
  const color = score >= 80 ? '#22c55e' : score >= 60 ? '#f59e0b' : '#ef4444';
  new Chart(el, {
    type: 'doughnut',
    data: {
      datasets: [{
        data: [score, 100 - score],
        backgroundColor: [color, '#27272a'],
        borderWidth: 0,
      }]
    },
    options: {
      responsive: false, cutout: '72%',
      plugins: { legend: { display: false }, tooltip: { enabled: false } }
    }
  });
})();
</script>
</body>
</html>
```

- [ ] **Step 2: Run integration tests**

```bash
pytest tests/test_dashboard.py -v
```

Expected: all 3 existing tests PASS.
- `test_dashboard_generates_html_file` — PASS
- `test_dashboard_html_contains_net_worth` — PASS
- `test_dashboard_is_self_contained` — PASS (no CDN URLs in output because all assets are inlined)

> **If `test_dashboard_is_self_contained` fails:** Check that `daisyui.min.css` and `alpine.min.js` were successfully downloaded in Task 1 and that `dashboard.py` reads them with `_read()`. The template must NOT contain any `cdn.jsdelivr.net` or `cdnjs.cloudflare.com` strings.

- [ ] **Step 3: Run the full test suite**

```bash
pytest -v
```

Expected: all tests pass. Fix any failures before continuing.

- [ ] **Step 4: Commit**

```bash
git add templates/dashboard.html.j2 dashboard.py
git commit -m "feat: rewrite dashboard template — 4-tab UI with DaisyUI + Alpine.js"
```

---

## Chunk 12: Update Integration Tests

### Task 12: Update test_dashboard.py for new template structure

**Files:**
- Modify: `tests/test_dashboard.py`

- [ ] **Step 1: Add new assertions for new template features**

Add these tests to `tests/test_dashboard.py` (keep all existing tests):

```python
def test_dashboard_has_four_tabs(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    assert "tab='overview'" in content or "tab=&apos;overview&apos;" in content or "overview" in content
    assert "Spending" in content
    assert "Goals" in content
    assert "Insights" in content

def test_dashboard_contains_health_score(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    assert "Financial Health Score" in content

def test_dashboard_contains_action_plan_section(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    assert "Action Plan" in content

def test_alpine_js_inlined(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    # Alpine.js is inlined — its signature function name must appear
    assert "Alpine" in content or "alpine" in content.lower()
```

- [ ] **Step 2: Run all tests**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Final commit**

```bash
git add tests/test_dashboard.py
git commit -m "test: add integration tests for new dashboard tabs and inlined assets"
```

---

## Chunk 13: End-to-End Verification

### Task 13: Manual smoke test + final commit

**Files:** No code changes — verification only.

- [ ] **Step 1: Run the full test suite one final time**

```bash
pytest -v --tb=short
```

Expected: 0 failures.

- [ ] **Step 2: Generate a dashboard against real data (if available) or test data**

```bash
python finance.py dashboard --no-open
```

Expected: `Dashboard generated: reports/dashboard.html` printed. File exists. No Python errors.

- [ ] **Step 3: Open the dashboard and verify manually**

```bash
open reports/dashboard.html
```

Check:
- [ ] All 4 tabs clickable and render content
- [ ] Overview: KPI cards show colored top-border accents
- [ ] Spending: Donut chart renders with legend
- [ ] Goals: Progress bars visible
- [ ] Insights: Health score ring + grade letter visible, cuts listed with saving amounts
- [ ] No console errors in browser DevTools
- [ ] No external network requests (check DevTools Network tab — should be empty after load)

- [ ] **Step 4: Tag the feature complete**

```bash
git tag ui-redesign-v1
```
