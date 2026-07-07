# finance-tracker — Product North-Star

- **Status:** CONFIRMED BY OWNER (Yash Inani) — 2026-07-07. This is the authoritative
  vision. Do NOT treat it as a draft; build toward it.
- **Stage:** pre-launch, private.

## Vision (owner's words)

> A financial platform where I can pull in all the current finances and accounts I
> have access to and, based on my spending habits, determine which spending can be
> most optimized in terms of **credit-card usage** — i.e. which credit card I should
> be using to get the most value out of how I actually spend.

## The one thing we are building right now (MVP scope)

A **credit-card usage optimizer**. Nothing else. The single end-to-end loop:

1. **Connect accounts** — user links a financial account via **Plaid**; pull accounts
   + transaction history. (More accounts/aggregators come later — see Roadmap.)
2. **Understand spending habits** — categorize transactions and quantify behavior
   (e.g. "how many times per month do I dine out," grocery spend, travel, etc.).
3. **Know the card landscape** — maintain a dataset of available credit cards and
   their rewards/rates/sign-up bonuses, sourced from the sibling
   `credit-card-bonuses-api` (https://github.com/yinani24/credit-card-bonuses-api).
4. **Recommend the optimal card** — a recommendation engine that maps the user's
   spending profile against the card dataset and says, with reasoning:
   *"Based on how much you dine out / spend on X, you should use **this** card
   because it gives you the most value."*
5. **Grow into a portfolio** — as spending data expands, recommend a **set** of cards
   (the right card per category) and how to combine them to maximize total value.

## Target user

Initially the owner (a spending-optimizer who wants to stop leaving credit-card
rewards on the table). Later: anyone who wants their card usage optimized to their
real spending.

## Explicitly OUT of scope for now

Budgeting, net-worth/investment tracking, bill pay, forecasting, multi-user/social,
and anything not in service of the card-optimization loop above. Keep the surface
small until the optimizer is genuinely useful.

## Success criteria (MVP)

- A user can link at least one account via Plaid and see their transactions
  categorized.
- The system quantifies spending by category (dining, groceries, travel, etc.).
- Given that profile, it recommends a specific credit card with a clear,
  data-backed rationale ("you'd earn ~$X more/year").
- Recommendations update as more spending data arrives.

## Delivery roadmap (phases → break each into PRDs/issues)

- **Phase 1 — Plaid works:** reliable account linking + transaction sync (sandbox
  first; live link is a manual owner step with real keys).
- **Phase 2 — Spending intelligence:** categorization + per-category habit metrics
  (dining frequency, category spend totals).
- **Phase 3 — Card dataset:** robust ingestion/caching/typing of card rewards data
  from credit-card-bonuses-api; add any missing fields upstream.
- **Phase 4 — Single-card recommendation:** engine that recommends the single best
  card for the user's profile, with value estimate + rationale.
- **Phase 5 — Multi-card portfolio:** recommend the optimal *combination* of cards
  by category as data expands.

## Open questions (need owner — answer under QUESTIONS FOR HUMAN)

1. **Optimization objective:** maximize cashback value, points value, or first-year
   value including sign-up bonuses? Or let the user choose?
2. **Card scope:** only cards the user already holds, all cards on the market, or
   both ("use your existing cards better" vs "apply for this new one")?
3. **Value model:** how do we price points/miles (fixed cents-per-point, or per
   redemption type)? A simple fixed-rate assumption is fine for MVP if acceptable.
4. **Starting categories:** which spending categories matter most first
   (dining/groceries/travel/gas)? Owner mentioned dining specifically.
