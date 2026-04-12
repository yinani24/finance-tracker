# Credit Card Recommendation Engine — Design Spec

## Overview

A backend-computed recommendation system that analyzes user spending patterns against available credit card offers to provide two types of advice:

1. **Next Card to Get** — which card to apply for next, ranked by sign-up bonus achievability
2. **Portfolio Analysis** — whether current cards are worth their fees, with better alternatives suggested

Uses the free [credit-card-bonuses-api](https://github.com/andenacitelli/credit-card-bonuses-api) dataset. Designed so category multiplier data slots in when contributed upstream.

## Data Model

### `spending_profiles`

Cached aggregation of a user's spending, refreshed on sync or on-demand.

| Column | Type | Description |
|--------|------|-------------|
| `id` | int, PK | |
| `user_id` | int, FK → users | |
| `period_start` | date | Start of analysis window |
| `period_end` | date | End of analysis window |
| `avg_monthly_spend` | float | Total average monthly spend |
| `category_breakdown_json` | text | JSON: `{"dining": 450, "travel": 800}` |
| `top_merchants_json` | text | JSON: `[{"name": "Amazon", "monthly_avg": 200}]` |
| `computed_at` | datetime | When this profile was computed |

One row per user (upserted on recomputation).

### `recommendation_snapshots`

Persisted recommendation results to avoid recomputation on every page load.

| Column | Type | Description |
|--------|------|-------------|
| `id` | int, PK | |
| `user_id` | int, FK → users | |
| `type` | string(20) | Enum: `next_card`, `portfolio_gap` |
| `results_json` | text | Ranked recommendations with explanations |
| `inputs_hash` | string(64) | Hash of spending profile + user cards — detects staleness |
| `computed_at` | datetime | When these results were computed |

One row per (user, type) pair. Unique constraint on `(user_id, type)`.

### Staleness strategy

`inputs_hash` is a SHA-256 of the spending profile contents + user's card list. When a Plaid sync or manual transaction add occurs, the snapshot service checks if the hash still matches. If not, recomputation is triggered on the next read.

## Service Layer

### `SpendingProfileService`

Owns transaction aggregation.

- `compute_profile(user_id, lookback_months=6)` — queries transactions table, computes:
  - Monthly average spend (total)
  - Spend by category (from Plaid's `personal_finance_category` primary values)
  - Top merchants by monthly average
  - Writes to `spending_profiles` table (upsert)
- `get_or_refresh(user_id)` — returns cached profile if `computed_at` is after the user's most recent transaction date; recomputes if stale

### `CardRecommendationService`

Pure-function engine. No DB dependency — takes inputs, returns outputs.

- `recommend_next_card(profile, user_cards) -> list[NextCardRecommendation]`
- `analyze_portfolio(profile, user_cards) -> PortfolioAnalysis`

Stateless and fully testable.

### `RecommendationSnapshotService`

Caching wrapper around `CardRecommendationService`.

- `get_recommendations(user_id, type) -> dict` — checks `inputs_hash`, returns cached or recomputes
- `invalidate(user_id)` — called after Plaid sync or transaction create/update

## Scoring Logic

### Next Card Scoring

```
score = bonus_value - annual_fee_first_year + credit_value

bonus_achievability:
  monthly_spend = profile.avg_monthly_spend
  months_to_hit = ceil(card.min_spend / monthly_spend)
  achievable = months_to_hit <= (card.bonus_days / 30)
```

Filters:
- Remove non-achievable bonuses (can't hit min spend in time)
- Remove cards user already owns (match by normalized card name against API card names; the existing `Card` model has `name` and `network` — add an optional `issuer` field for more reliable matching)
- Rank by score; boost cards with first-year fee waiver
- Return top 10 with explanation strings

### Portfolio Analysis Scoring

```
estimated_annual_value = (avg_monthly_spend * 12 * universalCashbackPercent / 100)
                       + sum(credit.value * credit.weight for credit in card.credits)

net_value = estimated_annual_value - annual_fee
```

- For each user card: compute `net_value`
- Flag cards where `net_value < 0` ("costing you money")
- For flagged cards: find alternatives with better `net_value` at same or lower annual fee
- Detect issuer gaps (future: supports 5/24-style rules in Phase 2)

### Future extensibility

When category multipliers land in the upstream API:
```
value = sum(category_spend * multiplier for each category) + credits - annual_fee
```

Single method change in `CardRecommendationService`.

## API Endpoints

New router: `/recommendations`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/recommendations/next-card` | Ranked next-card recommendations |
| GET | `/recommendations/portfolio` | Portfolio analysis |
| GET | `/recommendations/spending-profile` | User's computed spending profile |
| POST | `/recommendations/refresh` | Force recomputation |

All endpoints use `RecommendationSnapshotService` for fast repeat loads.

## Frontend

### Recommendations Page (`/recommendations`)

Two tabs:
- **Next Card** — ranked card list, each showing: card name/image, issuer, sign-up bonus, minimum spend, timeframe, personalized achievability note
- **Portfolio Analysis** — current cards with estimated annual value vs fee, flagged issues, suggested alternatives

### Dashboard Widget

- Compact card showing top 1-2 recommendations
- "View all" link to full Recommendations page
- Shows top spending category + best card match (future-proofed for multiplier data)

## Staleness Flow

1. User syncs Plaid or adds/updates transaction
2. API calls `snapshot_service.invalidate(user_id)`
3. Next request to `/recommendations/*` detects stale hash
4. Recomputes spending profile + recommendations
5. Caches new snapshot, returns fresh results

## Phase 2 (future, not in this implementation)

- Category multiplier data from upstream API contributions
- Chase 5/24 and issuer-specific application rules
- Preferred reward currency matching
- Card application tracking and cooldown periods
