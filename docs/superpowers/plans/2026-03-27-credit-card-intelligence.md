# Credit Card Intelligence & UI Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a credit card intelligence engine (optimizer + upgrade recommendations) and a production-grade Cards tab to the finance tracker dashboard, with UI polish to existing tabs, at 100% test coverage.

**Architecture:** Pure functions in `core/cards.py` → `compute_card_intelligence()` in `dashboard/analytics.py` → loaded by `dashboard/renderer.py` → rendered in new "Cards" tab in `templates/dashboard.html.j2`. The `cards` CLI command re-uses the same core functions.

**Tech Stack:** Python 3.11, pytest (100% coverage), Click, Rich, Pandas, Jinja2, Alpine.js (existing), Chart.js (existing), DaisyUI (existing)

**Spec:** `docs/superpowers/specs/2026-03-27-credit-card-intelligence-design.md`

---

## Task 1 — `core/cards.py`: engine functions + full test suite

**Files:**
- Create: `core/cards.py`
- Create: `tests/test_cards.py`

- [ ] **Step 1: Write all failing tests**

Create `tests/test_cards.py`:

```python
"""Tests for core/cards.py credit card intelligence engine."""
import pytest
import json
from core.cards import (
    load_cards,
    compute_card_value_per_category,
    compute_optimal_card_per_category,
    compute_card_annual_value,
    compute_missed_rewards,
    compute_upgrade_recommendations,
    CURATED_CARDS,
)


@pytest.fixture
def csp():
    return {
        "name": "Chase Sapphire Preferred",
        "issuer": "Chase",
        "annual_fee": 95,
        "reward_type": "points",
        "points_cpp": 0.0125,
        "rewards": {
            "Food & Dining": 3.0,
            "Transport": 2.0,
            "Subscriptions": 1.0,
            "Shopping": 1.0,
            "Health": 1.0,
            "Other": 1.0,
        },
    }


@pytest.fixture
def quicksilver():
    return {
        "name": "Quicksilver",
        "issuer": "Capital One",
        "annual_fee": 0,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {
            "Food & Dining": 1.5,
            "Transport": 1.5,
            "Subscriptions": 1.5,
            "Shopping": 1.5,
            "Health": 1.5,
            "Other": 1.5,
        },
    }


class TestLoadCards:
    def test_missing_file_returns_empty(self, tmp_path):
        result = load_cards(str(tmp_path / "cards.json"))
        assert result == {"cards": []}

    def test_loads_existing_file(self, tmp_path):
        data = {"cards": [{"name": "Test Card"}]}
        (tmp_path / "cards.json").write_text(json.dumps(data))
        result = load_cards(str(tmp_path / "cards.json"))
        assert result["cards"][0]["name"] == "Test Card"


class TestComputeCardValuePerCategory:
    def test_correct_arithmetic(self, csp):
        # 3.0 × 0.0125 × 4200 = 157.50
        result = compute_card_value_per_category(csp, "Food & Dining", 4200.0)
        assert result == pytest.approx(157.50)

    def test_fallback_to_other(self, csp):
        # "Entertainment" not in rewards → Other rate (1.0 × 0.0125 × 1200 = 15.0)
        result = compute_card_value_per_category(csp, "Entertainment", 1200.0)
        assert result == pytest.approx(15.0)

    def test_fallback_to_zero_when_other_absent(self):
        card = {"rewards": {"Food & Dining": 3.0}, "points_cpp": 0.01}
        result = compute_card_value_per_category(card, "Transport", 1000.0)
        assert result == pytest.approx(0.0)


class TestComputeOptimalCardPerCategory:
    def test_single_card_returns_itself(self, csp):
        result = compute_optimal_card_per_category([csp], {"Food & Dining": 4200.0})
        assert len(result) == 1
        assert result[0]["best_card"] == "Chase Sapphire Preferred"

    def test_multiple_cards_picks_highest_earner(self, csp, quicksilver):
        spending = {"Food & Dining": 4200.0, "Subscriptions": 500.0}
        result = compute_optimal_card_per_category([csp, quicksilver], spending)
        food = next(r for r in result if r["category"] == "Food & Dining")
        subs = next(r for r in result if r["category"] == "Subscriptions")
        # CSP dining: 3×0.0125=3.75% > QS 1.5×0.01=1.5% → CSP wins
        assert food["best_card"] == "Chase Sapphire Preferred"
        # QS subs: 1.5×0.01=1.5% > CSP 1.0×0.0125=1.25% → QS wins
        assert subs["best_card"] == "Quicksilver"

    def test_returns_sorted_by_annual_gain_descending(self, csp, quicksilver):
        spending = {"Food & Dining": 4200.0, "Subscriptions": 500.0}
        result = compute_optimal_card_per_category([csp, quicksilver], spending)
        gains = [r["annual_gain"] for r in result]
        assert gains == sorted(gains, reverse=True)

    def test_empty_cards_returns_empty(self):
        assert compute_optimal_card_per_category([], {"Food & Dining": 100.0}) == []

    def test_effective_pct_is_correct(self, csp):
        result = compute_optimal_card_per_category([csp], {"Food & Dining": 4200.0})
        # 3.0 × 0.0125 × 100 = 3.75%
        assert result[0]["effective_pct"] == pytest.approx(3.75)


class TestComputeCardAnnualValue:
    def test_net_value_is_gross_minus_fee(self, csp):
        result = compute_card_annual_value(csp, {"Food & Dining": 4200.0})
        assert result["name"] == "Chase Sapphire Preferred"
        assert result["gross_rewards"] == pytest.approx(157.50)
        assert result["annual_fee"] == 95
        assert result["net_value"] == pytest.approx(62.50)

    def test_zero_fee_card(self, quicksilver):
        result = compute_card_annual_value(quicksilver, {"Food & Dining": 1000.0})
        assert result["annual_fee"] == 0
        # 1.5 × 0.01 × 1000 = 15.0
        assert result["gross_rewards"] == pytest.approx(15.0)
        assert result["net_value"] == pytest.approx(15.0)


class TestComputeMissedRewards:
    def test_single_card_is_zero(self, csp):
        result = compute_missed_rewards({"Food & Dining": 4200.0}, [csp])
        assert result == pytest.approx(0.0)

    def test_empty_cards_is_zero(self):
        assert compute_missed_rewards({"Food & Dining": 1000.0}, []) == pytest.approx(0.0)

    def test_detects_missed_value(self):
        default_card = {
            "name": "Default", "annual_fee": 0, "points_cpp": 0.01,
            "rewards": {"Food & Dining": 1.0, "Transport": 1.0, "Other": 1.0},
        }
        better_card = {
            "name": "Better", "annual_fee": 0, "points_cpp": 0.01,
            "rewards": {"Food & Dining": 3.0, "Transport": 1.0, "Other": 1.0},
        }
        spending = {"Food & Dining": 1200.0, "Transport": 600.0}
        result = compute_missed_rewards(spending, [default_card, better_card])
        # Food: Better=3×0.01×1200=36 vs Default=1×0.01×1200=12 → missed=24
        # Transport: equal → missed=0
        assert result == pytest.approx(24.0)


class TestComputeUpgradeRecommendations:
    def test_empty_user_cards_returns_empty(self):
        assert compute_upgrade_recommendations({"Food & Dining": 5000.0}, []) == []

    def test_returns_at_most_two(self):
        basic = {"name": "Basic", "annual_fee": 0, "points_cpp": 0.01,
                 "rewards": {"Food & Dining": 1.0, "Other": 1.0}}
        result = compute_upgrade_recommendations({"Food & Dining": 5000.0}, [basic])
        assert len(result) <= 2

    def test_sorted_by_gain_over_best_descending(self):
        basic = {"name": "Basic", "annual_fee": 0, "points_cpp": 0.01,
                 "rewards": {"Food & Dining": 1.0, "Other": 1.0}}
        recs = compute_upgrade_recommendations({"Food & Dining": 5000.0}, [basic])
        gains = [r["gain_over_best"] for r in recs]
        assert gains == sorted(gains, reverse=True)

    def test_excludes_owned_cards(self):
        cfu = {"name": "Chase Freedom Unlimited", "annual_fee": 0, "points_cpp": 0.01,
               "rewards": {"Food & Dining": 3.0, "Other": 1.5}}
        basic = {"name": "Basic", "annual_fee": 0, "points_cpp": 0.01,
                 "rewards": {"Other": 1.0}}
        recs = compute_upgrade_recommendations({"Food & Dining": 5000.0}, [basic, cfu])
        assert all(r["name"].lower() != "chase freedom unlimited" for r in recs)

    def test_no_gain_returns_empty(self):
        super_card = {"name": "Super Card", "annual_fee": 0, "points_cpp": 0.01,
                      "rewards": {"Food & Dining": 10.0, "Other": 10.0}}
        recs = compute_upgrade_recommendations({"Food & Dining": 100.0}, [super_card])
        assert recs == []

    def test_why_field_is_non_empty_string(self):
        basic = {"name": "Basic", "annual_fee": 0, "points_cpp": 0.01,
                 "rewards": {"Food & Dining": 1.0, "Other": 1.0}}
        recs = compute_upgrade_recommendations({"Food & Dining": 5000.0}, [basic])
        for r in recs:
            assert isinstance(r["why"], str) and len(r["why"]) > 0


class TestCuratedCards:
    def test_has_eight_cards(self):
        assert len(CURATED_CARDS) == 8

    def test_all_have_required_fields(self):
        required = {"name", "issuer", "annual_fee", "reward_type", "points_cpp", "rewards"}
        for card in CURATED_CARDS:
            assert required.issubset(set(card.keys()))

    def test_all_have_other_in_rewards(self):
        for card in CURATED_CARDS:
            assert "Other" in card["rewards"], f"{card['name']} missing 'Other' in rewards"
```

- [ ] **Step 2: Run tests to confirm they all fail**

```bash
cd /Users/yashinani/Desktop/Projects/finance-tracker
pytest tests/test_cards.py -p no:cov 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'core.cards'`

- [ ] **Step 3: Create `core/cards.py`**

```python
"""Credit card intelligence engine: optimizer, value computation, and upgrade recommendations."""
from __future__ import annotations
import json
import os

CURATED_CARDS: list[dict] = [
    {
        "name": "Amex Gold",
        "issuer": "American Express",
        "annual_fee": 250,
        "reward_type": "points",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 4.0, "Transport": 1.0, "Shopping": 4.0,
                    "Subscriptions": 1.0, "Health": 1.0, "Other": 1.0},
    },
    {
        "name": "Chase Freedom Unlimited",
        "issuer": "Chase",
        "annual_fee": 0,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 3.0, "Transport": 1.5, "Shopping": 1.5,
                    "Subscriptions": 1.5, "Health": 1.5, "Other": 1.5},
    },
    {
        "name": "Citi Double Cash",
        "issuer": "Citi",
        "annual_fee": 0,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 2.0, "Transport": 2.0, "Shopping": 2.0,
                    "Subscriptions": 2.0, "Health": 2.0, "Other": 2.0},
    },
    {
        "name": "Capital One Venture X",
        "issuer": "Capital One",
        "annual_fee": 395,
        "reward_type": "miles",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 2.0, "Transport": 10.0, "Shopping": 2.0,
                    "Subscriptions": 2.0, "Health": 2.0, "Other": 2.0},
    },
    {
        "name": "Chase Freedom Flex",
        "issuer": "Chase",
        "annual_fee": 0,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 3.0, "Transport": 1.0, "Shopping": 5.0,
                    "Subscriptions": 1.0, "Health": 1.0, "Other": 1.0},
    },
    {
        "name": "Amex Blue Cash Preferred",
        "issuer": "American Express",
        "annual_fee": 95,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 3.0, "Transport": 3.0, "Shopping": 6.0,
                    "Subscriptions": 6.0, "Health": 1.0, "Other": 1.0},
    },
    {
        "name": "Wells Fargo Active Cash",
        "issuer": "Wells Fargo",
        "annual_fee": 0,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 2.0, "Transport": 2.0, "Shopping": 2.0,
                    "Subscriptions": 2.0, "Health": 2.0, "Other": 2.0},
    },
    {
        "name": "Discover it",
        "issuer": "Discover",
        "annual_fee": 0,
        "reward_type": "cashback",
        "points_cpp": 0.01,
        "rewards": {"Food & Dining": 5.0, "Transport": 1.0, "Shopping": 5.0,
                    "Subscriptions": 1.0, "Health": 1.0, "Other": 1.0},
    },
]


def load_cards(cards_path: str) -> dict:
    """Load card profiles from cards.json. Returns {"cards": []} if file does not exist."""
    if not os.path.exists(cards_path):
        return {"cards": []}
    with open(cards_path) as f:
        return json.load(f)


def compute_card_value_per_category(card: dict, category: str, annual_spend: float) -> float:
    """Return the annual reward value in dollars for a card in a specific spending category.

    Uses the card's reward rate for the category, falling back to "Other", then 0.0.
    annual_spend is the annualised spend (monthly_avg × 12).
    """
    rate = card["rewards"].get(category, card["rewards"].get("Other", 0.0))
    return round(annual_spend * rate * card["points_cpp"], 2)


def compute_optimal_card_per_category(cards: list, spending_by_category: dict) -> list:
    """For each category, find the card that maximises annual reward value.

    Returns list of dicts sorted by annual_gain (vs cards[0] default) descending:
    [{"category": str, "best_card": str, "annual_gain": float, "effective_pct": float}]
    """
    if not cards:
        return []
    default_card = cards[0]
    result = []
    for cat, annual_spend in spending_by_category.items():
        best = max(cards, key=lambda c: compute_card_value_per_category(c, cat, annual_spend))
        best_value = compute_card_value_per_category(best, cat, annual_spend)
        default_value = compute_card_value_per_category(default_card, cat, annual_spend)
        rate = best["rewards"].get(cat, best["rewards"].get("Other", 0.0))
        result.append({
            "category": cat,
            "best_card": best["name"],
            "annual_gain": round(best_value - default_value, 2),
            "effective_pct": round(rate * best["points_cpp"] * 100, 2),
        })
    return sorted(result, key=lambda x: x["annual_gain"], reverse=True)


def compute_card_annual_value(card: dict, spending_by_category: dict) -> dict:
    """Compute gross rewards, annual fee, and net value for a card.

    Returns {"name": str, "gross_rewards": float, "annual_fee": float, "net_value": float}.
    """
    gross = round(
        sum(compute_card_value_per_category(card, cat, spend)
            for cat, spend in spending_by_category.items()),
        2,
    )
    fee = card.get("annual_fee", 0)
    return {"name": card["name"], "gross_rewards": gross, "annual_fee": fee,
            "net_value": round(gross - fee, 2)}


def compute_missed_rewards(spending_by_category: dict, cards: list) -> float:
    """Annual dollars left on the table by always using cards[0] instead of the optimal card.

    Returns 0.0 when cards is empty or has only one card.
    """
    if len(cards) <= 1:
        return 0.0
    optimal = compute_optimal_card_per_category(cards, spending_by_category)
    return round(sum(max(item["annual_gain"], 0.0) for item in optimal), 2)


def compute_upgrade_recommendations(spending_by_category: dict, user_cards: list) -> list:
    """Return up to 2 CURATED_CARDS that improve on the user's best current card net value.

    Returns [] when user_cards is empty (no baseline to compare against).
    Each result dict: {"name", "annual_fee", "net_value", "gain_over_best", "why"}.
    """
    if not user_cards:
        return []

    owned = {c["name"].lower() for c in user_cards}
    user_best_net = max(
        compute_card_annual_value(c, spending_by_category)["net_value"] for c in user_cards
    )

    sorted_cats = sorted(spending_by_category.items(), key=lambda x: x[1], reverse=True)

    recs = []
    for curated in CURATED_CARDS:
        if curated["name"].lower() in owned:
            continue
        net = compute_card_annual_value(curated, spending_by_category)["net_value"]
        gain = round(net - user_best_net, 2)
        if gain <= 0:
            continue
        why = ""
        if sorted_cats:
            top_cat, top_annual = sorted_cats[0]
            rate = curated["rewards"].get(top_cat, curated["rewards"].get("Other", 0.0))
            why = f"{rate:g}x on {top_cat} — your #1 category at ${top_annual / 12:.0f}/mo"
        recs.append({"name": curated["name"], "annual_fee": curated["annual_fee"],
                     "net_value": round(net, 2), "gain_over_best": gain, "why": why})

    recs.sort(key=lambda x: x["gain_over_best"], reverse=True)
    return recs[:2]
```

- [ ] **Step 4: Run tests to confirm they all pass**

```bash
pytest tests/test_cards.py -v -p no:cov
```
Expected: All 23 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cards.py tests/test_cards.py
git commit -m "feat: add core/cards.py credit card intelligence engine with full test coverage"
```

---

## Task 2 — Data files: `cards.example.json` + `.gitignore`

**Files:**
- Create: `data/cards.example.json`
- Modify: `.gitignore`

- [ ] **Step 1: Create `data/cards.example.json`**

```json
{
  "cards": [
    {
      "name": "Chase Sapphire Preferred",
      "issuer": "Chase",
      "annual_fee": 95,
      "reward_type": "points",
      "points_cpp": 0.0125,
      "rewards": {
        "Food & Dining": 3.0,
        "Transport": 2.0,
        "Subscriptions": 1.0,
        "Shopping": 1.0,
        "Health": 1.0,
        "Other": 1.0
      }
    },
    {
      "name": "Capital One Quicksilver",
      "issuer": "Capital One",
      "annual_fee": 0,
      "reward_type": "cashback",
      "points_cpp": 0.01,
      "rewards": {
        "Food & Dining": 1.5,
        "Transport": 1.5,
        "Subscriptions": 1.5,
        "Shopping": 1.5,
        "Health": 1.5,
        "Other": 1.5
      }
    }
  ]
}
```

Field reference:
- `reward_type`: `"points"` | `"miles"` | `"cashback"`
- `points_cpp`: cents-per-point value. Chase points ≈ 0.0125, cashback = 0.01
- `rewards`: multiplier per $1 spent. `"Other"` is **required** as the fallback.

- [ ] **Step 2: Add `data/cards.json` to `.gitignore`**

Add after `data/goals.json`:
```
data/cards.json
```

- [ ] **Step 3: Run full test suite to confirm nothing broke**

```bash
pytest -p no:cov -q
```
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add data/cards.example.json .gitignore
git commit -m "feat: add cards.example.json schema and gitignore data/cards.json"
```

---

## Task 3 — `dashboard/analytics.py`: `compute_card_intelligence` + `build_context` update

**Files:**
- Modify: `dashboard/analytics.py`
- Modify: `tests/test_dashboard_data.py`

- [ ] **Step 1: Add failing tests to `tests/test_dashboard_data.py`**

Append at the bottom of the file (after the last test):

```python
class TestComputeCardIntelligence:
    def test_empty_cards_returns_empty_state(self, sample_df):
        from dashboard.analytics import compute_card_intelligence
        result = compute_card_intelligence(sample_df, {"cards": []})
        assert result["has_cards"] is False
        assert result["optimal_per_category"] == []
        assert result["card_values"] == []
        assert result["missed_rewards_annual"] == 0.0
        assert result["upgrade_recommendations"] == []

    def test_none_cards_returns_empty_state(self, sample_df):
        from dashboard.analytics import compute_card_intelligence
        result = compute_card_intelligence(sample_df, None)
        assert result["has_cards"] is False

    def test_empty_df_returns_empty_state(self):
        import pandas as pd
        from dashboard.analytics import compute_card_intelligence
        cards = {"cards": [{"name": "CSP", "annual_fee": 95, "reward_type": "points",
                            "points_cpp": 0.0125,
                            "rewards": {"Food & Dining": 3.0, "Other": 1.0}}]}
        result = compute_card_intelligence(pd.DataFrame(), cards)
        assert result["has_cards"] is False

    def test_full_returns_correct_structure(self, sample_df):
        from datetime import date
        from dashboard.analytics import compute_card_intelligence
        csp = {"name": "Chase Sapphire Preferred", "annual_fee": 95,
               "reward_type": "points", "points_cpp": 0.0125,
               "rewards": {"Food & Dining": 3.0, "Transport": 2.0,
                           "Subscriptions": 1.0, "Other": 1.0}}
        qs  = {"name": "Quicksilver", "annual_fee": 0,
               "reward_type": "cashback", "points_cpp": 0.01,
               "rewards": {"Food & Dining": 1.5, "Transport": 1.5,
                           "Subscriptions": 1.5, "Other": 1.5}}
        result = compute_card_intelligence(
            sample_df, {"cards": [csp, qs]}, today=date(2026, 3, 15)
        )
        assert result["has_cards"] is True
        assert result["missed_rewards_annual"] > 0
        assert len(result["card_values"]) == 2
        assert len(result["optimal_per_category"]) >= 1

    def test_build_context_without_cards_has_card_intel_key(
        self, sample_df, sample_accounts, sample_goals
    ):
        ctx = build_context(sample_df, sample_accounts, sample_goals, today=TODAY)
        assert "card_intel" in ctx
        assert ctx["card_intel"]["has_cards"] is False
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
pytest tests/test_dashboard_data.py::TestComputeCardIntelligence -p no:cov -v
```
Expected: `ImportError` or `AttributeError` — `compute_card_intelligence` does not exist yet.

- [ ] **Step 3: Update `dashboard/analytics.py`**

Add import at top of file (after existing imports):

```python
from core.cards import (
    compute_card_value_per_category as _card_value,
    compute_optimal_card_per_category,
    compute_card_annual_value,
    compute_missed_rewards,
    compute_upgrade_recommendations,
)
```

Add `compute_card_intelligence` function (insert before `build_context`):

```python
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

    # Build annualised spending by category from the last 3 months
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
```

Update `build_context` signature (add `cards=None` before `today`):

```python
def build_context(df: pd.DataFrame, accounts: dict, goals: dict, cards: dict | None = None, today: date | None = None) -> dict:
```

Update the docstring return description to add `card_intel`.

Add the call inside `build_context` body (add after `top_merchants = ...` line):

```python
card_intel = compute_card_intelligence(df, cards, today=today)
```

Add `"card_intel": card_intel` to the returned dict.

- [ ] **Step 4: Run new + existing tests to confirm all pass**

```bash
pytest tests/test_dashboard_data.py -p no:cov -v
```
Expected: All tests PASS (existing + new).

- [ ] **Step 5: Run full suite**

```bash
pytest -p no:cov -q
```
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add dashboard/analytics.py tests/test_dashboard_data.py
git commit -m "feat: add compute_card_intelligence to analytics and update build_context"
```

---

## Task 4 — `dashboard/renderer.py`: load `cards.json`

**Files:**
- Modify: `dashboard/renderer.py`
- Modify: `tests/test_dashboard.py`

- [ ] **Step 1: Add failing tests to `tests/test_dashboard.py`**

Replace the existing `test_dashboard_load_files_missing_csv` test body (it currently checks a 3-tuple — update it to check the 4-tuple and add a new cards test):

**Update** `test_dashboard_load_files_missing_csv`:
```python
def test_dashboard_load_files_missing_csv(tmp_path):
    """Cover FileNotFoundError path in _load_files."""
    from dashboard import _load_files
    df, accounts, goals, cards = _load_files(str(tmp_path))
    assert df.empty
    assert accounts == {"accounts": []}
    assert goals["monthly_target"] == 0.0
    assert cards == {"cards": []}
```

**Update** `test_dashboard_load_files_with_goals`:
```python
def test_dashboard_load_files_with_goals(tmp_path):
    """Cover goals.json load path in _load_files."""
    import json
    from dashboard import _load_files
    goals_data = {"monthly_target": 300.0, "goals": [], "monthly_streak": {}}
    (tmp_path / "goals.json").write_text(json.dumps(goals_data))
    _, _, goals, cards = _load_files(str(tmp_path))
    assert goals["monthly_target"] == 300.0
    assert cards == {"cards": []}
```

**Add** new test at end of file:
```python
def test_dashboard_load_files_with_cards(tmp_path):
    """Cover cards.json load path in _load_files."""
    import json
    from dashboard import _load_files
    cards_data = {"cards": [{"name": "Test Card"}]}
    (tmp_path / "cards.json").write_text(json.dumps(cards_data))
    _, _, _, cards = _load_files(str(tmp_path))
    assert cards["cards"][0]["name"] == "Test Card"
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
pytest tests/test_dashboard.py::test_dashboard_load_files_missing_csv tests/test_dashboard.py::test_dashboard_load_files_with_cards -p no:cov -v
```
Expected: FAIL — `_load_files` returns 3-tuple, unpacking to 4 raises `ValueError`.

- [ ] **Step 3: Update `dashboard/renderer.py`**

Update `_load_files` signature, docstring, body, and return:

```python
def _load_files(data_dir: str) -> tuple[pd.DataFrame, dict, dict, dict]:
    """Load transactions, accounts, goals, and cards from the data directory.

    Returns:
        A 4-tuple of (transactions DataFrame, accounts dict, goals dict, cards dict).
    """
    store_path    = f"{data_dir}/transactions.csv"
    accounts_path = f"{data_dir}/accounts.json"
    goals_path    = f"{data_dir}/goals.json"
    cards_path    = f"{data_dir}/cards.json"

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

    cards = {"cards": []}
    if os.path.exists(cards_path):
        with open(cards_path) as f:
            cards = json.load(f)

    return df, accounts, goals, cards
```

Update `build_dashboard` to unpack and pass cards:

```python
def build_dashboard(data_dir: str = "data", output_path: str = "reports/dashboard.html") -> str:
    ...
    df, accounts, goals, cards = _load_files(data_dir)
    context = build_context(df, accounts, goals, cards=cards)
    ...
```

- [ ] **Step 4: Run all tests to confirm they pass**

```bash
pytest -p no:cov -q
```
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/renderer.py tests/test_dashboard.py
git commit -m "feat: load cards.json in renderer and pass to build_context"
```

---

## Task 5 — `main.py`: `cards` CLI command

**Files:**
- Modify: `main.py`
- Modify: `tests/test_cli_summary.py`

- [ ] **Step 1: Add failing tests to `tests/test_cli_summary.py`**

Append at the bottom:

```python
def test_cards_command_no_cards_file(tmp_path):
    """Shows empty state message when data/cards.json does not exist."""
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cli, ["cards", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "No cards configured" in result.output


def test_cards_command_with_cards(runner_with_data):
    """Shows portfolio table when cards.json is present."""
    import json
    runner, tmp_path = runner_with_data
    cards = {
        "cards": [{
            "name": "Chase Sapphire Preferred",
            "issuer": "Chase",
            "annual_fee": 95,
            "reward_type": "points",
            "points_cpp": 0.0125,
            "rewards": {"Food & Dining": 3.0, "Transport": 2.0,
                        "Subscriptions": 1.0, "Other": 1.0},
        }]
    }
    (tmp_path / "cards.json").write_text(json.dumps(cards))
    result = runner.invoke(cli, ["cards", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Chase Sapphire Preferred" in result.output
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
pytest tests/test_cli_summary.py::test_cards_command_no_cards_file tests/test_cli_summary.py::test_cards_command_with_cards -p no:cov -v
```
Expected: FAIL — `No such command 'cards'`.

- [ ] **Step 3: Add `cards` command to `main.py`**

Add after the `dashboard` command (before `if __name__ == "__main__"`):

```python
# ── cards ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--data-dir", default="data", hidden=True)
def cards(data_dir: str) -> None:
    """Show credit card portfolio, optimizer, and upgrade recommendations."""
    from core.cards import load_cards
    from dashboard.analytics import compute_card_intelligence

    card_data = load_cards(f"{data_dir}/cards.json")
    if not card_data.get("cards"):
        console.print("[yellow]No cards configured. Copy data/cards.example.json to data/cards.json and edit.[/yellow]")
        return

    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    df = store.load()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])

    intel = compute_card_intelligence(df, card_data)

    # Portfolio table
    t = Table(title="Card Portfolio", show_header=True)
    t.add_column("Card")
    t.add_column("Annual Fee", justify="right")
    t.add_column("Est. Rewards/yr", justify="right")
    t.add_column("Net Value", justify="right")
    for cv in intel["card_values"]:
        color = "green" if cv["net_value"] > 0 else "red"
        t.add_row(
            cv["name"],
            f"${cv['annual_fee']:.2f}",
            f"${cv['gross_rewards']:.2f}",
            f"[{color}]${cv['net_value']:.2f}[/{color}]",
        )
    console.print(t)

    # Missed rewards callout
    if intel["missed_rewards_annual"] >= 5:
        console.print(
            f"\n[yellow]You're leaving [bold]${intel['missed_rewards_annual']:.2f}[/bold]/yr "
            "on the table by not using the optimal card per category.[/yellow]"
        )

    # Top 3 category optimizations
    top_opts = [o for o in intel["optimal_per_category"][:3] if o["annual_gain"] > 0]
    if top_opts:
        t2 = Table(title="Category Optimizer (Top 3)", show_header=True)
        t2.add_column("Category")
        t2.add_column("Use This Card")
        t2.add_column("Annual Gain", justify="right")
        for item in top_opts:
            t2.add_row(item["category"], item["best_card"], f"[green]+${item['annual_gain']:.2f}[/green]")
        console.print(t2)

    # Top upgrade recommendation
    if intel["upgrade_recommendations"]:
        rec = intel["upgrade_recommendations"][0]
        console.print(
            f"\n[blue]Top upgrade:[/blue] {rec['name']} — {rec['why']} "
            f"(+${rec['gain_over_best']:.2f}/yr over your best card)"
        )
```

- [ ] **Step 4: Run new + existing CLI tests**

```bash
pytest tests/test_cli_summary.py -p no:cov -v
```
Expected: All tests PASS.

- [ ] **Step 5: Run full suite**

```bash
pytest -p no:cov -q
```
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_cli_summary.py
git commit -m "feat: add cards CLI command for portfolio summary and upgrade picks"
```

---

## Task 6 — `templates/dashboard.html.j2`: Cards tab + dashboard tests

**Files:**
- Modify: `templates/dashboard.html.j2`
- Modify: `tests/test_dashboard.py`

- [ ] **Step 1: Update failing tests in `tests/test_dashboard.py`**

**Rename** `test_dashboard_has_four_tabs` → `test_dashboard_has_five_tabs` and add Cards assertion:

```python
def test_dashboard_has_five_tabs(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    assert "overview" in content
    assert "Spending" in content
    assert "Goals" in content
    assert "Insights" in content
    assert "Cards" in content
```

**Add** new tests at end of file:

```python
def test_dashboard_renders_cards_empty_state(runner_with_data, tmp_path):
    """Cards tab renders empty state when no cards.json present."""
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    assert "cards" in content.lower()
    assert "No Cards Configured" in content


def test_dashboard_renders_cards_tab_with_data(runner_with_data, tmp_path):
    """Cards tab shows portfolio table when cards.json is present."""
    import json
    runner, data_dir = runner_with_data
    cards = {"cards": [{
        "name": "Chase Sapphire Preferred", "issuer": "Chase",
        "annual_fee": 95, "reward_type": "points", "points_cpp": 0.0125,
        "rewards": {"Food & Dining": 3.0, "Transport": 2.0,
                    "Subscriptions": 1.0, "Other": 1.0},
    }]}
    (data_dir / "cards.json").write_text(json.dumps(cards))
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    assert "Chase Sapphire Preferred" in content
    assert "Card Portfolio" in content
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
pytest tests/test_dashboard.py::test_dashboard_has_five_tabs tests/test_dashboard.py::test_dashboard_renders_cards_empty_state -p no:cov -v
```
Expected: FAIL — "Cards" not in template yet.

- [ ] **Step 3: Add Cards tab button to the tab bar in `templates/dashboard.html.j2`**

In `dashboard.html.j2`, find the tab bar section (lines 99-104) and add the Cards button:

**Old:**
```html
  <div class="tab-bar" style="margin-bottom:24px">
    <button class="tab-btn" :class="tab==='overview'  ? 'active' : ''" @click="tab='overview'">Overview</button>
    <button class="tab-btn" :class="tab==='spending'  ? 'active' : ''" @click="tab='spending'">Spending</button>
    <button class="tab-btn" :class="tab==='goals'     ? 'active' : ''" @click="tab='goals'">Goals</button>
    <button class="tab-btn" :class="tab==='insights'  ? 'active' : ''" @click="tab='insights'">Insights</button>
  </div>
```

**New:**
```html
  <div class="tab-bar" style="margin-bottom:24px">
    <button class="tab-btn" :class="tab==='overview'  ? 'active' : ''" @click="tab='overview'">Overview</button>
    <button class="tab-btn" :class="tab==='spending'  ? 'active' : ''" @click="tab='spending'">Spending</button>
    <button class="tab-btn" :class="tab==='goals'     ? 'active' : ''" @click="tab='goals'">Goals</button>
    <button class="tab-btn" :class="tab==='insights'  ? 'active' : ''" @click="tab='insights'">Insights</button>
    <button class="tab-btn" :class="tab==='cards'     ? 'active' : ''" @click="tab='cards'">Cards</button>
  </div>
```

- [ ] **Step 4: Add Cards tab panel before the footer line**

In `dashboard.html.j2`, find:
```html
  </div>{# end insights #}

  <div style="font-size:0.68rem;color:var(--muted);text-align:right;margin-top:20px">Generated: {{ generated_at }}</div>
```

Insert the entire Cards panel between `</div>{# end insights #}` and the footer `<div>`:

```html
  {# ════════════════════════════════════════════
     CARDS TAB
  ════════════════════════════════════════════ #}
  <div x-show="tab==='cards'" x-cloak>

    {% if card_intel.has_cards %}

      {# 1. Portfolio Table #}
      <div class="card" style="margin-bottom:12px">
        <div class="section-label">Card Portfolio</div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Card</th>
              <th style="text-align:right">Annual Fee</th>
              <th style="text-align:right">Est. Rewards/yr</th>
              <th style="text-align:right">Net Value</th>
              <th style="text-align:right">Status</th>
            </tr>
          </thead>
          <tbody>
            {% for cv in card_intel.card_values %}
            <tr>
              <td style="font-weight:500">{{ cv.name }}</td>
              <td style="text-align:right;color:var(--muted)">${{ cv.annual_fee | format_currency }}</td>
              <td style="text-align:right;color:var(--green)">${{ cv.gross_rewards | format_currency }}</td>
              <td style="text-align:right;font-weight:600;color:{% if cv.net_value > 10 %}var(--green){% elif cv.net_value < -10 %}var(--red){% else %}var(--amber){% endif %}">
                {% if cv.net_value >= 0 %}+{% endif %}${{ cv.net_value | format_currency }}
              </td>
              <td style="text-align:right">
                {% if cv.net_value > 10 %}<span class="badge badge-down">Earning</span>
                {% elif cv.net_value < -10 %}<span class="badge badge-up">Costs You</span>
                {% else %}<span class="badge badge-neutral">Break Even</span>{% endif %}
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

      {# 2. Missed Rewards Callout #}
      {% if card_intel.missed_rewards_annual >= 5 %}
      <div style="padding:14px 16px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:10px;margin-bottom:12px">
        <div style="font-size:0.82rem;font-weight:600;color:var(--amber)">
          💳 You left <strong>${{ card_intel.missed_rewards_annual | format_currency }}</strong>/yr in rewards on the table by routing all spending through one card.
        </div>
        <div style="font-size:0.72rem;color:var(--muted);margin-top:4px">Use the optimizer below to see where to switch cards.</div>
      </div>
      {% endif %}

      {# 3. Category Optimizer #}
      {% if card_intel.optimal_per_category %}
      <div class="card" style="margin-bottom:12px">
        <div class="section-label">Category Optimizer</div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Best Card</th>
              <th style="text-align:right">Effective %</th>
              <th style="text-align:right">Annual Gain vs Default</th>
            </tr>
          </thead>
          <tbody>
            {% for item in card_intel.optimal_per_category %}
            <tr {% if item.annual_gain > 20 %}style="background:rgba(34,197,94,0.04)"{% endif %}>
              <td style="font-weight:500">{{ item.category }}</td>
              <td>{{ item.best_card }}</td>
              <td style="text-align:right;color:var(--blue)">{{ "%.1f" | format(item.effective_pct) }}%</td>
              <td style="text-align:right;color:{% if item.annual_gain > 0 %}var(--green){% else %}var(--muted){% endif %}">
                {% if item.annual_gain > 0 %}+${{ item.annual_gain | format_currency }}{% else %}—{% endif %}
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      {% endif %}

      {# 4. Upgrade Picks #}
      {% if card_intel.upgrade_recommendations %}
      <div>
        <div class="section-label">Upgrade Picks</div>
        <div style="display:flex;flex-direction:column;gap:8px">
          {% for rec in card_intel.upgrade_recommendations %}
          <div class="insight-card">
            <div class="insight-icon" style="background:rgba(59,130,246,0.1)">💳</div>
            <div style="flex:1">
              <div style="font-size:0.84rem;font-weight:600;margin-bottom:3px">{{ rec.name }}</div>
              <div style="font-size:0.74rem;color:var(--muted)">{{ rec.why }}</div>
              <div style="font-size:0.72rem;color:var(--muted);margin-top:3px">Annual fee: ${{ rec.annual_fee | format_currency }}</div>
            </div>
            <div style="font-size:0.82rem;font-weight:700;color:var(--green);flex-shrink:0;white-space:nowrap">+${{ rec.gain_over_best | format_currency }}/yr</div>
          </div>
          {% endfor %}
        </div>
      </div>
      {% endif %}

    {% else %}
      <div class="card" style="text-align:center;padding:48px 24px">
        <div style="font-size:2.2rem;margin-bottom:12px">💳</div>
        <div style="font-size:0.95rem;font-weight:600;margin-bottom:8px">No Cards Configured</div>
        <div style="font-size:0.78rem;color:var(--muted);max-width:340px;margin:0 auto">
          Copy <code>data/cards.example.json</code> to <code>data/cards.json</code> and fill in your card details to unlock optimization recommendations.
        </div>
      </div>
    {% endif %}

  </div>{# end cards #}
```

- [ ] **Step 5: Run all dashboard tests**

```bash
pytest tests/test_dashboard.py -p no:cov -v
```
Expected: All tests PASS (including new + renamed).

- [ ] **Step 6: Run full suite**

```bash
pytest -p no:cov -q
```
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add templates/dashboard.html.j2 tests/test_dashboard.py
git commit -m "feat: add Cards tab to dashboard with portfolio, optimizer, and upgrade picks"
```

---

## Task 7 — UI polish to existing dashboard tabs

**Files:**
- Modify: `templates/dashboard.html.j2`

No new tests needed — existing tests cover the rendered output. Changes are purely CSS/HTML presentation.

- [ ] **Step 1: Update KPI card accent styles (left border instead of top gradient)**

In the `<style>` block, find and replace the four `card-accent-*::before` rules:

**Old (lines 32-35):**
```css
  .card-accent-green::before  { content:''; display:block; height:2px; background:linear-gradient(90deg,var(--green),transparent); border-radius:12px 12px 0 0; margin:-20px -20px 16px; }
  .card-accent-red::before    { content:''; display:block; height:2px; background:linear-gradient(90deg,var(--red),transparent);   border-radius:12px 12px 0 0; margin:-20px -20px 16px; }
  .card-accent-blue::before   { content:''; display:block; height:2px; background:linear-gradient(90deg,var(--blue),transparent);  border-radius:12px 12px 0 0; margin:-20px -20px 16px; }
  .card-accent-purple::before { content:''; display:block; height:2px; background:linear-gradient(90deg,var(--purple),transparent);border-radius:12px 12px 0 0; margin:-20px -20px 16px; }
```

**New:**
```css
  .card-accent-green  { border-left: 3px solid var(--green)  !important; padding-left: 17px; }
  .card-accent-red    { border-left: 3px solid var(--red)    !important; padding-left: 17px; }
  .card-accent-blue   { border-left: 3px solid var(--blue)   !important; padding-left: 17px; }
  .card-accent-purple { border-left: 3px solid var(--purple) !important; padding-left: 17px; }
```

- [ ] **Step 2: Improve progress bar rounding and bar-fill rounding**

Find:
```css
  .bar-track { flex:1; background:var(--surface2); border-radius:4px; height:7px; overflow:hidden; }
  .bar-fill  { height:7px; border-radius:4px; }
```

Replace with:
```css
  .bar-track { flex:1; background:var(--surface2); border-radius:999px; height:7px; overflow:hidden; }
  .bar-fill  { height:7px; border-radius:999px; }

```

Find:
```css
  .progress-track { background:var(--surface2); border-radius:6px; height:6px; }
  .progress-fill  { height:6px; border-radius:6px; background:linear-gradient(90deg,var(--blue),var(--cyan)); }
```

Replace with:
```css
  .progress-track { background:var(--surface2); border-radius:999px; height:6px; }
  .progress-fill  { height:6px; border-radius:999px; background:linear-gradient(90deg,var(--blue),var(--cyan)); }
```

- [ ] **Step 3: Improve Insights tab section separation**

Find the divider between Actionable Cuts and Action Plan sections. After the closing `{% endif %}` of the Actionable Cuts block and before `{# Action Plan #}`, add a visual separator:

**Find:**
```html
    {% endif %}

    {# Action Plan #}
```

**Replace with:**
```html
    {% endif %}

    <div style="height:1px;background:var(--surface2);margin:16px 0"></div>

    {# Action Plan #}
```

- [ ] **Step 4: Improve empty-state for goals tab**

Find:
```html
    <div class="card" style="font-size:0.8rem;color:var(--muted)">
      No named goals. Run: <code>finance goal set "Emergency Fund" --target 10000 --by 2026-12</code>
    </div>
```

Replace with:
```html
    <div class="card" style="text-align:center;padding:32px 24px">
      <div style="font-size:1.5rem;margin-bottom:10px">🎯</div>
      <div style="font-size:0.85rem;font-weight:600;margin-bottom:6px">No named goals yet</div>
      <div style="font-size:0.75rem;color:var(--muted)">
        Run: <code>finance goal set "Emergency Fund" --target 10000 --by 2026-12</code>
      </div>
    </div>
```

- [ ] **Step 5: Improve health score grade display**

Find the health score grade display in the Insights tab:
```html
          <div style="font-size:1.3rem;font-weight:700;color:{% if health.score >= 80 %}var(--green){% elif health.score >= 60 %}var(--amber){% else %}var(--red){% endif %}">{{ health.grade }}</div>
```

Replace with:
```html
          <div style="font-size:1.4rem;font-weight:800;letter-spacing:-0.02em;color:{% if health.score >= 80 %}var(--green){% elif health.score >= 60 %}var(--amber){% else %}var(--red){% endif %}">{{ health.grade }}</div>
```

- [ ] **Step 6: Run full test suite to confirm nothing broke**

```bash
pytest -p no:cov -q
```
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add templates/dashboard.html.j2
git commit -m "ui: polish KPI accent borders, progress bars, and section separation"
```

---

## Task 8 — `CLAUDE.md`: update docs

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add `cards` command to Commands section**

In `CLAUDE.md`, find:
```markdown
python3 main.py dashboard             # generates + opens reports/dashboard.html
```

Add after it:
```markdown
python3 main.py cards                 # show card portfolio, optimizer, and upgrade picks
```

- [ ] **Step 2: Add `core/cards.py` to Key Modules table**

Find the Key Modules table and add a row after `core/goals.py`:

```markdown
| `core/cards.py` | `load_cards()`, `compute_optimal_card_per_category()`, `compute_card_annual_value()`, `compute_missed_rewards()`, `compute_upgrade_recommendations()`. `CURATED_CARDS` = 8 hardcoded upgrade candidates. |
```

- [ ] **Step 3: Add `data/cards.json` to gitignore section**

In the gitignore section, add:
```
data/cards.json
```

- [ ] **Step 4: Run full test suite with coverage enforcement**

```bash
pytest
```
Expected: All tests PASS, 100% coverage.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with cards command and core/cards.py module"
```

---

## Final Verification

- [ ] **Run full suite with coverage**

```bash
pytest
```
Expected: All tests PASS, 100% coverage, no warnings.

- [ ] **Smoke test the dashboard**

```bash
python3 main.py dashboard --no-open --data-dir data 2>/dev/null || echo "No data dir — expected"
```

- [ ] **Smoke test the cards command**

```bash
python3 main.py cards 2>/dev/null || echo "No data dir — expected"
```
