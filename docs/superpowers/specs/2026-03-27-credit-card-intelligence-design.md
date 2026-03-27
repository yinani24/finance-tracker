# Credit Card Intelligence & UI Improvements — Design Spec

**Date:** 2026-03-27
**Status:** Approved

---

## Overview

Add a credit card intelligence layer to the finance tracker that helps the user:
1. Identify which of their existing cards to use per spending category (optimizer)
2. Evaluate each card's net annual value (rewards earned − annual fee)
3. Surface how much reward value was left on the table by not routing spend optimally
4. Recommend 1–2 upgrade cards from a curated list based on actual spending patterns

Additionally, improve the existing dashboard UI to production-grade quality without restructuring existing analytics.

---

## User Context

**Cards owned:**
- Chase Sapphire Preferred (actively used — all current spending flows through this card)
- BofA Travel Card
- BofA Standard Credit Card
- Capital One Quicksilver
- Discover Standard (must keep — oldest card, credit history anchor)

**Data coverage:** Chase and BofA transactions are imported. Discover and Quicksilver have no transactions yet — card profiles will be configured manually. Importers for those cards may be added in a future phase.

**Constraint:** Discover card is never a candidate for removal.

---

## Architecture

### Data Flow Addition

```
data/cards.json  (new, gitignored)
       │
       ▼
core/cards.py  ←  pure functions, no I/O
       │
       ▼
dashboard/analytics.py  →  compute_card_intelligence()
       │
       ▼
dashboard/renderer.py  →  loads cards.json alongside accounts.json + goals.json
       │
       ▼
templates/dashboard.html.j2  →  new "Cards" tab
```

### New Files

| File | Purpose |
|------|---------|
| `core/cards.py` | Pure card engine functions + `CURATED_CARDS` constant |
| `data/cards.json` | User's card profiles (gitignored) |
| `data/cards.example.json` | Committed example with schema documentation |
| `tests/test_cards.py` | Full unit tests for core/cards.py |

### Modified Files

| File | Change |
|------|--------|
| `dashboard/analytics.py` | Add `compute_card_intelligence()`, update `build_context()` |
| `dashboard/renderer.py` | Load `cards.json` in `_load_files()` |
| `templates/dashboard.html.j2` | Add Cards tab + UI polish to existing tabs |
| `tests/test_dashboard.py` | Cover new Cards tab rendering |
| `tests/test_dashboard_data.py` | Cover `compute_card_intelligence()` |
| `main.py` | Add `cards` CLI command |
| `tests/test_cli_summary.py` | Cover `cards` CLI command |
| `.gitignore` | Add `data/cards.json` |
| `CLAUDE.md` | Document new command and cards.json schema |

---

## Data Model

### `data/cards.json`

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
    }
  ]
}
```

**Field definitions:**
- `rewards` — points or miles earned per $1 spent in each category
- `reward_type` — `"points"` | `"miles"` | `"cashback"`
- `points_cpp` — cents-per-point valuation; cashback cards use `0.01`, Chase points `0.0125`, travel cards vary

**Effective cashback % per category** = `rewards[category] × points_cpp × 100`

---

## Core Engine: `core/cards.py`

### Constants

```python
CURATED_CARDS: list[dict]  # ~8 well-known upgrade candidates
```

Curated list (hardcoded, versioned in code):
- Amex Gold (4x dining, 4x groceries, $250 fee)
- Chase Freedom Unlimited (1.5% everything, no fee)
- Citi Double Cash (2% everything, no fee)
- Capital One Venture X (2x everything + travel perks, $395 fee)
- Chase Freedom Flex (5% rotating, no fee)
- Amex Blue Cash Preferred (6% groceries, $95 fee)
- Wells Fargo Active Cash (2% everything, no fee)
- Discover it (5% rotating, 1% otherwise, no fee — used as reference for existing Discover card)

### Functions

#### `load_cards(cards_path: str) -> dict`
Loads `cards.json`. Returns `{"cards": []}` if file does not exist.

#### `compute_card_value_per_category(card: dict, category: str, monthly_spend: float) -> float`
Returns estimated annual reward value (in dollars) for a single card + category combination.

```
annual_value = monthly_spend × 12 × rewards[category] × points_cpp
```

#### `compute_optimal_card_per_category(cards: list, spending_by_category: dict) -> list`
For each category in spending_by_category, returns the card that maximises reward value.

Returns list of dicts:
```python
[{"category": str, "best_card": str, "annual_gain": float, "effective_pct": float}]
```
Sorted by `annual_gain` descending.

#### `compute_card_annual_value(card: dict, spending_by_category: dict) -> dict`
Returns net annual value for a card:
```python
{
  "name": str,
  "gross_rewards": float,   # total rewards earned across all categories
  "annual_fee": float,
  "net_value": float,       # gross_rewards - annual_fee
}
```

#### `compute_missed_rewards(spending_by_category: dict, cards: list) -> float`
Returns the total annual dollar value left on the table by routing all spending through the first card in the list (the "default" card) instead of using the optimal card per category.

#### `compute_upgrade_recommendations(spending_by_category: dict, user_cards: list) -> list`
Compares user's spending pattern against `CURATED_CARDS`. Returns up to 2 recommendations where a curated card's net annual value exceeds the user's current best card net value.

Returns list of dicts:
```python
[{
  "name": str,
  "annual_fee": float,
  "net_value": float,
  "gain_over_best": float,   # net_value - user's best card net_value
  "why": str,                # human-readable reason
}]
```
Sorted by `gain_over_best` descending. Excludes cards the user already owns.

---

## Analytics Integration

### `compute_card_intelligence(df, cards, today=None) -> dict`

Added to `dashboard/analytics.py`. Follows the same signature pattern as existing compute_ functions.

```python
def compute_card_intelligence(df: pd.DataFrame, cards: dict, today: date | None = None) -> dict:
    ...
    return {
        "optimal_per_category": [...],
        "card_values": [...],
        "missed_rewards_annual": float,
        "upgrade_recommendations": [...],
        "has_cards": bool,
    }
```

Returns `{"has_cards": False, ...empty lists...}` when `cards["cards"]` is empty — allows the template to render a graceful empty state.

**Spending by category** is derived from the last 3 months of transaction data (annualised), consistent with how `compute_category_trends` works.

### `build_context()` update

`cards` parameter added:
```python
def build_context(df, accounts, goals, cards, today=None) -> dict:
```

`card_intel` key added to the returned context dict.

---

## Renderer Update

`_load_files()` in `dashboard/renderer.py` loads `cards.json` alongside existing files. Falls back to `{"cards": []}` if absent (no file = graceful empty state in the Cards tab).

`build_context()` call updated to pass `cards`.

---

## CLI Command

```bash
python3 main.py cards [--data-dir DATA_DIR]
```

Prints a Rich table summary:
- Per-card: annual fee, estimated rewards, net value
- Top 3 category optimizations (category → use this card instead → saves $X/yr)
- Missed rewards total
- Top upgrade recommendation (if any)

Follows existing Click + `--data-dir` pattern for test isolation.

---

## Dashboard: Cards Tab

New tab button added to the tab bar. Four sections:

### 1. Portfolio Table
Columns: Card | Annual Fee | Est. Rewards/yr | Net Value | Status

Status badge:
- Green "Earning" — net value > 0
- Red "Costs You" — net value < 0 (fee exceeds rewards earned)
- Amber "Break Even" — within $10 of zero

### 2. Category Optimizer Table
Columns: Category | Best Card | Effective % | Est. Annual Gain vs. Default

Highlights rows where the gain > $20/yr.

### 3. Missed Rewards Callout
Single prominent callout card:
> "You left **$X** in rewards on the table over the past year by routing all spending through Chase Sapphire Preferred."

Hidden when missed rewards < $5 (noise threshold).

### 4. Upgrade Picks
Up to 2 recommendation cards. Each shows:
- Card name + issuer
- Annual fee
- Why it fits your spending (e.g., "4x on dining — your #1 category at $X/mo")
- Estimated net gain over your current best card

---

## UI Improvements (Existing Tabs)

Targeted visual polish — no structural analytics changes:

- **KPI cards:** improve label → value → sub-label hierarchy; add subtle colour-coded left border instead of top gradient
- **Section labels:** consistent uppercase + tracking across all tabs
- **Progress bars:** rounded caps, gradient fill consistent across Goals and Spending tabs
- **Tables:** tighter row spacing, better column alignment
- **Empty states:** replace plain text with styled placeholder cards
- **Health score:** improve grade badge size and contrast
- **Insights tab:** better visual separation between Cuts and Action Plan sections

---

## Testing Strategy

All new code follows TDD with 100% coverage enforced.

### `tests/test_cards.py`
Unit tests for every function in `core/cards.py`:
- `test_load_cards_missing_file` — returns empty default
- `test_compute_card_value_per_category` — correct arithmetic
- `test_compute_optimal_card_per_category_single_card` — degenerate case
- `test_compute_optimal_card_per_category_multiple_cards` — picks highest earner
- `test_compute_card_annual_value` — gross rewards, fee deduction, net
- `test_compute_card_annual_value_no_fee` — fee=0 edge case
- `test_compute_missed_rewards_zero_when_one_card` — single card, no missed value
- `test_compute_missed_rewards_positive` — detects suboptimal routing
- `test_compute_upgrade_recommendations_excludes_owned` — no dupes
- `test_compute_upgrade_recommendations_returns_top_two` — sorted correctly
- `test_compute_upgrade_recommendations_empty_when_no_gain` — no false positives

### `tests/test_dashboard_data.py`
- `test_compute_card_intelligence_empty_cards` — graceful empty state
- `test_compute_card_intelligence_empty_df` — no transactions
- `test_compute_card_intelligence_full` — end-to-end with fixture data

### `tests/test_dashboard.py`
- `test_dashboard_renders_cards_tab` — Cards tab present in rendered HTML
- `test_dashboard_renders_cards_empty_state` — graceful when no cards

### `tests/test_cli_summary.py`
- `test_cards_command_no_cards_file` — runs without error, shows empty state
- `test_cards_command_with_cards` — shows portfolio summary

---

## Sign Conventions & Edge Cases

- All `spending_by_category` values passed to card functions are **positive** (expense amounts, already abs'd)
- Cards with `annual_fee: 0` are always candidates — net value = gross rewards
- If a category in `spending_by_category` has no matching key in `card.rewards`, fall back to the `"Other"` rewards rate
- `compute_missed_rewards` treats the first card in `cards["cards"]` as the "current default" card
- `compute_upgrade_recommendations` never recommends a card the user already owns (matched by name, case-insensitive)

---

## Gitignore Addition

```
data/cards.json
```

`data/cards.example.json` is committed as schema documentation.

---

## Out of Scope (Future Phase)

- Discover and Quicksilver CSV importers
- Dynamic card database (market-wide, auto-updated)
- Sign-up bonus tracking
- Credit score impact analysis
- Spending projections / "if you switch cards" simulations
