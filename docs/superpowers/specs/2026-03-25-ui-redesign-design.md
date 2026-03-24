# Finance Dashboard UI Redesign — Design Spec
**Date:** 2026-03-25
**Status:** Approved

---

## Overview

Redesign the existing single-scroll HTML dashboard into a tabbed, high-density interface with deep financial analysis. The new dashboard adds a financial health score, per-category trend analysis, actionable spending cuts, and a forward-looking action plan. Built using DaisyUI + Alpine.js (both inlined for offline use) replacing the current minimal custom CSS.

---

## Goals

1. Replace the single-scroll layout with a top-tab navigation (Overview / Spending / Goals / Insights)
2. Add a `dashboard_data.py` computation layer — pure functions, independently testable
3. Implement a financial health score (0–100, letter grade) based on savings rate, spending trends, and goal progress
4. Surface actionable cut recommendations with exact dollar savings per category
5. Generate a 3-month forward action plan from the data
6. Render per-category 3-month sparkline trends with directional badges (↑↓→)
7. Show spending as % of gross income
8. All new logic written test-first (TDD): tests in `tests/test_dashboard_data.py` written before implementation

---

## Architecture

### Data Flow

```
transactions.csv + accounts.json + goals.json
        ↓
  dashboard_data.py  (pure functions, no I/O, no side effects)
        ↓  returns a single typed dict: DashboardContext
  dashboard.py       (loads files → calls data layer → renders template)
        ↓
  reports/dashboard.html
```

### New / Modified Files

| File | Change | Purpose |
|------|--------|---------|
| `dashboard_data.py` | NEW | All computation logic — health score, insights, trends, cuts |
| `dashboard.py` | MODIFIED | Thin renderer — file I/O + calls `dashboard_data` + Jinja2 render |
| `templates/dashboard.html.j2` | REWRITTEN | New tabbed design with DaisyUI + Alpine.js |
| `templates/daisyui.min.css` | NEW | DaisyUI v5 CSS, downloaded and stored locally for offline use |
| `templates/alpine.min.js` | NEW | Alpine.js v3, downloaded and stored locally for offline use |
| `tests/test_dashboard_data.py` | NEW | TDD tests for all computation functions |
| `tests/test_dashboard.py` | MODIFIED | Integration tests updated for new template structure |

### `dashboard_data.py` Interface

The module exposes a single entry point:

```python
def build_context(df: pd.DataFrame, accounts: dict, goals: dict) -> dict:
    """
    Takes raw data (no file I/O) and returns a complete context dict
    for the Jinja2 template.

    Args:
        df: transactions DataFrame (columns: date, amount, merchant, category,
            account, source, is_income, is_savings, notes)
        accounts: full parsed accounts.json dict, e.g.
            {"accounts": [{"name": ..., "type": ..., "balance": ..., ...}]}
        goals: full parsed goals.json dict, e.g.
            {"monthly_target": 500.0, "goals": [...], "monthly_streak": {...}}
    """
```

Internally composed of focused pure functions:

```python
def compute_kpis(df, accounts: dict, goals: dict) -> dict
    # net_worth, income, expenses, saved, monthly_target, savings_rate
    # accounts and goals are the full JSON dicts as loaded from file

def compute_category_trends(df, months=3) -> list[dict]
    # per-category: current_amount, prior_amounts[], pct_change, direction

def compute_health_score(kpis, category_trends, goals: dict) -> dict
    # score (0-100), grade (A/B/C/D/F), passing/failing areas

def compute_actionable_cuts(df, category_trends) -> list[dict]
    # specific cuts: description, potential_saving, priority

def compute_action_plan(cuts, goals: dict, kpis) -> list[dict]
    # up to 3 prioritized steps; fewer returned if fewer than 3 cuts exist

def compute_spending_pct_of_income(df, income: float) -> list[dict]
    # per-category: name, amount, pct_of_income

def compute_account_balances(accounts: dict) -> list[dict]
    # name, balance, type, share_of_total

def compute_top_merchants(df, month: str) -> list[dict]
    # top 10 merchants for the given month (format: "YYYY-MM")
    # used by Overview tab; defaults to current calendar month
```

`dashboard.py` is reduced to:
```python
def build_dashboard(data_dir, output_path):
    df, accounts, goals = _load_files(data_dir)
    context = build_context(df, accounts, goals)
    html = _render(context)
    _write(html, output_path)
```

---

## UI Design

### Layout: Top Tab Navigation

```
┌─ Header: "Finance Dashboard"  ·  Last updated  ·  [Month picker] ─────┐
│                                                                         │
│  [ Overview ]  [ Spending ]  [ Goals ]  [ Insights ]                   │
│                                                                         │
│  ─── tab content ────────────────────────────────────────────────────  │
└─────────────────────────────────────────────────────────────────────────┘
```

Tab switching handled by Alpine.js (`x-data="{ tab: 'overview' }"`), no page reload.

### Design System

| Token | Value |
|-------|-------|
| Background | `#09090b` (zinc-950) |
| Card surface | `#18181b` (zinc-900) |
| Border | `#27272a` (zinc-800) |
| Muted text | `#71717a` (zinc-500) |
| Font | Inter (embedded via `@font-face` or Google Fonts link) |
| Green accent | `#22c55e` |
| Red accent | `#ef4444` |
| Blue accent | `#3b82f6` |
| Purple accent | `#a855f7` |
| Amber accent | `#f59e0b` |

KPI cards have a 2px colored top-border accent. Cards hover to lighter border on `:hover`.

### Overview Tab

- 4 KPI cards: Net Worth (green), Income (neutral), Expenses (red), Saved (blue)
  - Each shows value, MoM change badge (↑↓→), sub-label
- Monthly spending bar chart (12 months, current month highlighted red)
- Account balances with proportional progress bars
- Top merchants table: rank, merchant, category badge, tx count, total

### Spending Tab

- Period selector: This Month / 3 Months / 6 Months / Year
- Row 1: Category donut (with legend) + Income vs Expenses bar chart with glow + savings rate callout
- Row 2: Per-category sparklines — 3 mini-bars per category, MoM delta badge, month labels
- Row 3: "Where did my money go" — horizontal bars as % of gross income

### Goals Tab

- Monthly savings streak: calendar dots (green = hit, red = missed, gray = future)
- Monthly target card: amount saved vs goal, progress bar, days remaining
- Named goals: per-goal progress bar (gradient), deadline, required monthly contribution, on-track status

### Insights Tab

- **Health Score ring** (donut chart): 0–100 score, letter grade (A/B/C/D/F), passing/failing tags
- **Actionable Cuts**: cards with icon, description, potential monthly saving (right-aligned green)
- **3-Month Action Plan**: numbered steps (1/2/3) with colored priority indicators, plain-language descriptions

---

## Health Score Algorithm

Score is computed from weighted sub-scores (total 100 pts):

| Component | Weight | Pass condition |
|-----------|--------|---------------|
| Savings rate | 30 pts | ≥ 20% of income = full points, scales linearly |
| Spending trend | 25 pts | No category up >20% MoM = full; each offending category -8 pts |
| Goal progress | 25 pts | All goals on track = full; each at-risk goal -12 pts |
| Subscription ratio | 10 pts | Subscriptions < 8% of income = full; >15% = 0 |
| Emergency fund | 10 pts | Emergency fund goal >50% complete = full |

Grade scale (non-overlapping):

| Grade | Range |
|-------|-------|
| A | 90–100 |
| B+ | 80–89 |
| B | 75–79 |
| C | 60–74 |
| D | 45–59 |
| F | 0–44 |

Savings rate sub-score scales linearly: `min(savings_rate / 0.20, 1.0) × 30`. A 0% savings rate yields 0 pts; 10% yields 15 pts; ≥20% yields full 30 pts.

---

## Actionable Cuts Logic

For each expense category:
1. Compute 3-month average spend
2. If current month > average × 1.15 → flag as "trending high", recommended cut = `current - average`
3. For Subscriptions: parse individual merchant charges, list them explicitly, flag any >$15/mo as individually cuttable
4. For Transport: if avg rides > 10/mo, flag short-trip optimization
5. Sort cuts by `potential_saving` descending

---

## Action Plan Generation

Select up to 3 cuts by `potential_saving` descending. If fewer than 3 cuts exist, return only as many steps as there are cuts (never pad with empty steps).

For each step:
- Assign a target month label using the format `"Month YYYY"` (e.g., `"April 2026"`), sequentially from the current month
- Frame as a forward-looking statement: "By [Month YYYY], [action] → saves $X → enables [goal progress]"
- If a named goal has `pct_complete < expected_pct` (where `expected_pct = months_elapsed / total_months × 100`), that goal is considered **at-risk** and the plan step links the cut savings directly to the goal shortfall

**At-risk definition:** A goal is at-risk when `current_amount / target_amount < months_elapsed_since_created / total_months_to_deadline`. This is the progress-to-date ratio vs the time-elapsed ratio.

---

## TDD Approach

All `dashboard_data.py` functions are written **after** their tests pass. Test file structure:

```python
# tests/test_dashboard_data.py

class TestComputeKPIs:
    def test_savings_rate_calculated_correctly(...)
    def test_zero_income_returns_zero_savings_rate(...)
    def test_monthly_target_comparison(...)

class TestCategoryTrends:
    def test_pct_change_direction_up(...)
    def test_pct_change_direction_down(...)
    def test_handles_missing_prior_months(...)
    def test_three_months_returned(...)

class TestHealthScore:
    def test_perfect_score_all_conditions_met(...)
    def test_savings_rate_zero_yields_zero_savings_pts(...)
    def test_savings_rate_10pct_yields_15_pts(...)
    def test_savings_rate_at_or_above_20pct_yields_full_30_pts(...)
    def test_high_spending_trend_deducts_points(...)
    def test_grade_A_at_90(...)
    def test_grade_B_plus_at_80(...)
    def test_grade_B_at_75(...)
    def test_grade_C_at_60(...)
    def test_grade_D_at_45(...)
    def test_grade_F_at_44(...)

class TestActionableCuts:
    def test_category_flagged_when_15pct_above_average(...)
    def test_category_not_flagged_below_threshold(...)
    def test_subscriptions_listed_individually(...)
    def test_cuts_sorted_by_saving_desc(...)

class TestActionPlan:
    def test_returns_up_to_three_steps(...)
    def test_returns_fewer_steps_when_fewer_cuts(...)
    def test_step_links_to_at_risk_goal(...)
    def test_month_labels_are_sequential_format_month_yyyy(...)

class TestSpendingPctOfIncome:
    def test_pct_calculated_correctly(...)
    def test_zero_income_returns_zero_pct(...)

class TestAccountBalances:
    def test_share_of_total_calculated_correctly(...)
    def test_negative_balance_handled(...)

class TestTopMerchants:
    def test_filters_to_given_month(...)
    def test_returns_top_10_by_spend(...)
    def test_includes_tx_count(...)
```

Tests use pytest fixtures with synthetic DataFrames — no file I/O in tests.

---

## Asset Inlining

To maintain the self-contained offline-capable HTML requirement:

1. **DaisyUI** — use the prebuilt standalone CSS bundle from jsDelivr:
   `https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.css`
   DaisyUI v4 ships a standalone CSS file that does not require Tailwind as a build step. Save as `templates/daisyui.min.css`. (DaisyUI v5 is a Tailwind plugin only — use v4 for the standalone bundle.)
2. **Custom design tokens** — the design system colors (zinc-950 background, card surfaces, accents) are written as plain CSS variables in the template, not reliant on Tailwind utilities.
3. `templates/alpine.min.js` — download Alpine.js v3.14 from unpkg:
   `https://unpkg.com/alpinejs@3.14.8/dist/cdn.min.js`
4. `dashboard.py` reads both files and passes them to the template (same pattern as `chart.min.js`)
5. Template inlines them: `<style>{{ daisyui_css }}</style>` and `<script>{{ alpine_js }}</script>`

---

## Out of Scope (This Phase)

- Credit card optimization tab (Phase 3)
- Period selector functionality (UI rendered, filter logic deferred to follow-up)
- Plaid sync integration
- PDF/CSV import changes
- Mobile layout optimization

---

## Phase 3 Preview (Credit Optimization)

Planned as a separate spec. Will add a **Credit** tab with:
- "Leaving money on the table" — best card per category based on actual spend
- "Optimize your wallet" — which existing card to use per merchant
- "Get a new card" — recommendations with signup bonus + annual fee breakeven
