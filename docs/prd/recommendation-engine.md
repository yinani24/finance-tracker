# PRD — Credit-Card Recommendation Engine (Phases 4–5)

- **Status:** DRAFT (agent-authored), reconciled 2026-07-10 against shipped code; decomposition
  status re-synced 2026-07-18. Documents the owner-confirmed objective from `docs/prd/PRODUCT.md`
  and reconciles it against the engine already in the codebase. Decomposition slices 1–3 have
  **shipped**: dollar-valued bonuses (#24), flat ongoing rewards (#35), and **category-aware
  earn (slice 3, #38 → option A)** — the curated `app/data/card_category_rates.json` table is
  wired into `_ongoing_value` and was verified/blessed via #171. The #38 card-data decision is
  **resolved** (in-repo curated table). The remaining gaps are slices 4–5 (per-category
  best-held-card assignment and Phase-5 multi-card combination), which are now **unblocked**
  (issue #177 tracks slice 4). Open Question 1 (point valuation) is resolved with a live,
  flagged 1.0¢/point default.
- **Owner north-star:** `docs/prd/PRODUCT.md` (CONFIRMED). This PRD refines Phases 4–5
  of that roadmap; it does not override any confirmed decision there.
- **Depends on:** Phase 2 spending intelligence (`spending_profile.py`, transaction
  enrichment #11) and Phase 3 card dataset (`card_bonuses.py` over the sibling
  `credit-card-bonuses-api`).

---

## Problem

The product's whole reason to exist is step 4 of the MVP loop in `PRODUCT.md`:

> *"Based on how much you dine out / spend on X, you should use **this** card because
> it gives you the most value."*

The owner confirmed the ranking objective (Decision #1): **total first-year value =
ongoing rewards value PLUS sign-up bonuses over the first year**, across **both** the
cards the user already holds and new cards worth applying for (Decision #2).

There is already a recommendation engine in the codebase
(`app/services/card_recommendation.py`, surfaced via `/recommendations/*` and cached in
`recommendation_snapshot.py`). **But it does not yet implement the confirmed objective.**
See "Current implementation vs. target" — the ongoing-rewards half of first-year value,
and the category breakdown that is the product's premise, are not modeled. This PRD names
the gap so it can be decomposed into shippable Stage-1 issues.

## Goals

- Rank recommendations by **total estimated first-year value** as the owner defined it:
  `sign-up bonus (best achievable offer) + first-year ongoing rewards + statement credits
  − annual fee`.
- Make ongoing rewards **category-aware**: earn is driven by the user's
  `category_breakdown` (dining first), not a single flat cashback rate.
- Serve **both** modes distinctly (Decision #2):
  - **Optimize current wallet** — for each card the user holds, is it pulling its weight,
    and which held card should be used for which category?
  - **Apply for new** — which not-yet-held card adds the most first-year value.
- Every recommendation carries a **plain-language, data-backed rationale** with the dollar
  figure ("you'd earn ~$X more/year"), per the MVP success criteria.
- Deterministic + cacheable: recommendations recompute when the spending profile or card
  dataset changes (the `recommendation_snapshot` inputs-hash pattern already does this).

## Non-goals (for this PRD)

- Phase 6+ concerns from `PRODUCT.md` OUT-of-scope list (budgeting, net worth, forecasting).
- Real-time per-transaction "use this card now" prompts — batch profile-based ranking only.
- Automated card applications or any action beyond *recommending*.
- Multi-user tuning — single-owner correctness first.

## User stories

1. As the owner, I connect my accounts and see, for my actual spending, the **one new
   card** that would give me the most total value in year one, with the math shown.
2. As the owner, I see whether each card I **already hold** is worth its annual fee given
   how I spend, and which of my cards to use for dining vs. groceries vs. travel.
3. As the owner, when I dine out more, my recommendations shift toward dining-strong cards
   without me doing anything.
4. As the owner, I understand *why* a card is recommended (bonus achievability + ongoing
   category earn + credits − fee), not just a ranked list.

## Functional requirements

### FR1 — First-year value model
`first_year_value(card, profile) = best_achievable_signup_bonus_value
+ first_year_ongoing_rewards(card, profile) + statement_credit_value(card) − annual_fee`.

- **Sign-up bonus:** **shipped** — `_best_achievable_offer` filters to the offer tiers the
  user can hit (achievability = `min_spend / avg_monthly_spend ≤ offer_days / 30`) then
  picks the highest-**dollar-value** one. Bonus value is dollar-denominated via
  `_bonus_value_usd` (USD entries at face value, points/miles at `points_value_cents` per
  point, default 1.0¢) — so bonuses are comparable to cashback dollars (shipped in #28,
  see Open Question 1). Keep.
- **Ongoing rewards:** `Σ_category (monthly_spend[category] × 12 × reward_rate(card,
  category))`. The **flat** version — `avg_monthly_spend × 12 × universalCashbackPercent`
  via the shared `_ongoing_value` helper — is **shipped** (#37) in both `recommend_next_card`
  and `analyze_portfolio`. The **category-aware** upgrade (wiring `profile.category_breakdown`
  into per-category `reward_rate(card, category)`) is the remaining gap and needs the
  per-category reward rates from FR3 (blocked by #38, Open Question 3).
- **Credits:** already implemented — `Σ (credit.value × credit.weight)`. Keep, but confirm
  `weight` semantics (Open Question 2).

### FR2 — Two recommendation modes
- **`next_card`** (apply-for-new): exclude discontinued, no-offer, and already-held cards;
  rank remaining by FR1. *(Today's `recommend_next_card` ranks by bonus − fee + credits and
  omits ongoing rewards — extend it to FR1.)*
- **`portfolio` / `optimize-wallet`** (held cards): for each held card, compute net
  first-year value and a per-category "best held card" assignment; flag
  `good | underperforming | costing_money`; suggest a strictly-better lower/equal-fee
  alternative when one exists. *(Today's `analyze_portfolio` uses only flat
  `universalCashbackPercent` — extend to category-aware FR1.)*

### FR3 — Category reward rates from the dataset
The engine must map each card's rewards to internal categories (the enrichment taxonomy
from #11: `dining, groceries, travel, transport, shopping, bills, entertainment, health,
income, other`). Today the consumed dataset exposes only `universalCashbackPercent` (a flat
rate) — there is **no per-category multiplier field**. Resolve via Open Question 3:
either enrich upstream `credit-card-bonuses-api` with category rates, or fall back to flat
cashback for v1 and treat category-awareness as a fast-follow.

### FR4 — Rationale
Each result includes a human-readable `explanation` string and the component breakdown
(bonus, ongoing, credits, fee) so the UI can render "you'd earn ~$X more/year."

### FR5 — Freshness
Recommendations are cached per user keyed on a hash of (spending profile JSON + card
dataset JSON); a change in either invalidates the snapshot. *(Already implemented in
`recommendation_snapshot.py` / `card_insight_engine.py` — preserve this contract.)*

## Current implementation vs. target (the gap)

| Capability | Confirmed target | Today in `card_recommendation.py` |
|---|---|---|
| Sign-up bonus value | ✅ counts | ✅ `_best_achievable_offer` + achievability check; **dollar-valued** via `_bonus_value_usd` (cents-per-point, #28) |
| Statement credits | ✅ counts | ✅ `Σ value×weight` |
| Annual fee | ✅ subtract | ✅ subtracted (first-year waivers honored, #42) |
| **Ongoing rewards (year 1)** | ✅ **half the objective** | ✅ **flat model shipped** (#37) — `next_card` score is `bonus + ongoing − fee + credits`; `_ongoing_value` shared with `analyze_portfolio` |
| **Category-aware earn** | ✅ product premise (dining first) | ✅ **shipped (slice 3, #38→A)** — `_ongoing_value` reads `category_breakdown` and per-category curated rates (`app/data/card_category_rates.json`), flat-cashback fallback; used by **both** modes; rates blessed via #171 |
| Held vs. new distinction | ✅ two modes | ✅ both `recommend_next_card` and `analyze_portfolio` compute category-aware first-year value |
| Rationale w/ $ value | ✅ | ✅ dollar-denominated explanation with the four FR1 components |
| **Per-category best-held-card** | ✅ "use THIS card for dining" (User Story 2) | ❌ **the remaining gap** — `analyze_portfolio` values each held card in isolation but names no per-category winner (**slice 4**, issue #177) |

**Bottom line:** the plumbing, caching, API surface, dollar-denominated sign-up-bonus math
(#24), the first-year ongoing-rewards term (#35), and **category-aware earn** (slice 3, #38→A;
`_ongoing_value` drives earn from `category_breakdown` and the curated per-category rate table,
blessed via #171) are all in place. The remaining engine work is **slice 4** — the per-category
"best held card" assignment that answers *"which of my cards should I use for dining vs.
groceries?"* (User Story 2, issue #177) — and **slice 5** (Phase-5 multi-card combination).
Both are now **unblocked**; the #38 data-source dependency is resolved.

## Success criteria

- For a profile with a known category breakdown, `next_card` ranks by full FR1 first-year
  value (bonus + ongoing + credits − fee), and moving spend between categories changes the
  ranking in the expected direction (unit-testable with fixture cards).
- `optimize-wallet` labels each held card and names the best held card per category.
- Every recommendation exposes the four value components + a rationale string.
- No regression: existing `/recommendations/*` endpoints and snapshot caching keep working.

## Open questions (QUESTIONS FOR HUMAN)

1. **Point/mile valuation.** *(Assumption live — override optional; no longer blocking.)*
   `PRODUCT.md` Open Question 3 authorizes proceeding with a fixed cents-per-point
   assumption for MVP and flagging it. Done: bonuses are dollar-valued at a default
   **1.0¢/point** (`_bonus_value_usd`, threaded as `points_value_cents` through
   `recommend_next_card` / `_best_achievable_offer`; shipped #28, covered by
   `test_card_recommendation_service.py`), so bonus points and cashback dollars now rank on
   the same scale. **Decision still open only if you want to change the default:** confirm
   1.0¢/point, or supply per-issuer / per-redemption values. Absent a change, 1.0¢ stands.
2. **`credit.weight` semantics.** Credits are valued as `value × weight`. Is `weight` the
   probability/utilization you'd actually realize a credit (e.g. 0.9 = "worth 90% to me")?
   Confirm, so the rationale can explain it.
3. **Category reward rates.** The consumed card dataset exposes only a flat
   `universalCashbackPercent`, no per-category multipliers. To make recommendations truly
   "based on how much you dine out," we need category rates. Preferred path:
   (a) enrich the sibling `credit-card-bonuses-api` with per-category earn rates (bigger,
   cross-repo), or (b) ship v1 on flat cashback and treat category-awareness as a
   fast-follow? Recommendation: **(b) for the first shippable slice**, then (a).
4. **First-year vs. steady-state.** "First-year value" front-loads the sign-up bonus. Do
   you also want a **second-year / ongoing** view (value once the bonus is gone) so a card
   isn't recommended purely on a one-time bonus? Not blocking v1; flag for Phase 5.

## Proposed decomposition (Stage 1 — status)

1. ✅ **SHIPPED (#28).** Cents-per-point valuation so bonus points and cashback dollars are
   comparable (default 1.0¢/point; Open Question 1 assumption is live and flagged).
2. ✅ **SHIPPED (#37).** First-year ongoing-rewards term using flat
   `universalCashbackPercent`, via the shared `_ongoing_value` helper (both modes).
3. ✅ **SHIPPED (#38 → option A).** Category-aware earn — `_ongoing_value` wires
   `profile.category_breakdown` into per-category rates from the curated in-repo
   `app/data/card_category_rates.json` (flat-cashback fallback), used by both modes. The
   #38 data-source decision resolved to the in-repo curated table; rates verified/blessed
   via #171.
4. 🔜 **UNBLOCKED — issue #177.** `optimize-wallet` per-category "best held card"
   assignment (which held card to use for dining vs. groceries vs. travel; User Story 2).
5. Depends on (4). Phase 5 — multi-card portfolio combination (right card per category
   across the wallet).

**Net:** slices 1–3 are done. Slice 4 (per-category best-held-card, #177) is now unblocked
and is the next shippable engine slice; slice 5 (multi-card combination) follows it. The #38
category-rate data-source dependency is resolved — engine work is no longer gated on it.

Ref: `docs/prd/PRODUCT.md` (Phases 4–5, Decisions #1–2, Open Questions 3–4).
