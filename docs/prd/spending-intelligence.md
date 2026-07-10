# PRD — Spending Intelligence (Phase 2)

- **Status:** DRAFT (agent-authored). Documents the owner-confirmed **Phase 2** of
  `docs/prd/PRODUCT.md` and reconciles it against what already ships in the codebase.
  This PRD does not override any confirmed decision in `PRODUCT.md`; it names the gap
  between the shipped baseline and the Phase-2 promise so it can be decomposed into
  Stage-1 issues.
- **Owner north-star:** `docs/prd/PRODUCT.md` (CONFIRMED). Phase 2 there:
  *"categorization + per-category habit metrics (dining frequency, category spend
  totals)."*
- **Depends on:** Phase 1 transaction ingest (Plaid sync `plaid_service.py`; manual
  CSV import `statement_import.py`) and the enrichment layer (#11).
- **Feeds:** Phase 4–5 recommendation engine (`docs/prd/recommendation-engine.md`),
  which consumes the `SpendingProfile` this capability produces. **Note:** the
  category-aware *earn* upgrade in that PRD is blocked on a card-side data-source
  decision (#38). Everything in *this* PRD is **consumer-side only and needs no card
  data**, so it is independently shippable while #38 is pending.

---

## Problem

Step 2 of the MVP loop in `PRODUCT.md` is *"Understand spending habits — categorize
transactions and quantify behavior (e.g. how many times per month do I dine out,
grocery spend, travel, etc.)."* The recommendation engine's entire premise —
*"based on how much you dine out…"* — rests on this layer producing an accurate,
category-resolved picture of how the user actually spends.

A working baseline already exists (see "Current implementation vs. target"), but two
things are true: (1) it has never been captured in a PRD, so its scope, success
criteria, and open questions are undocumented; and (2) the literal headline metric the
owner named — **"how many times per month do I dine out"** — is not yet exposed as a
first-class per-month figure. This PRD documents the shipped baseline and scopes the
unblocked slices that close the gap.

## Goals

- Every ingested transaction (Plaid **and** manual import) carries an internal category
  from the fixed taxonomy, assigned at the ingest boundary (vendor-agnostic).
- Produce a per-user `SpendingProfile` that quantifies, per category: **spend** (money
  per month) and **frequency** (how often), plus overall monthly spend and top
  merchants — dining first, per the owner's priority.
- Expose the "how many times per month do I dine out" metric as a first-class,
  per-month number (not a raw period total the caller must normalize itself).
- Keep the profile **fresh**: recompute when spending data changes so downstream
  recommendations track reality.

## Non-goals (for this PRD)

- Card matching, reward rates, or any card-side data — that is Phases 3–5
  (`recommendation-engine.md`), and is where the #38 blocker lives.
- Budgeting, forecasting, net-worth, or cash-flow projection — explicitly out of scope
  in `PRODUCT.md`.
- Merchant-logo/enrichment-vendor integration beyond the existing pluggable hook (the
  no-op provider is the default; a real vendor is a separate decision).

## User stories

- As the owner, I can see my spending broken down by category (dining, groceries,
  travel, …) as a monthly average, so I know where my money goes.
- As the owner, I can see **how many times per month** I dine out (and transact in each
  category), so "frequency" — not just dollars — informs recommendations.
- As the owner, my profile reflects newly-synced or newly-imported transactions without
  a manual rebuild.
- As the recommendation engine, I can read one `SpendingProfile` object and get both the
  per-category monthly spend and the per-category frequency I need to rank cards.

## Functional requirements

### FR1 — Categorization at ingest
Every transaction is mapped to exactly one of the fixed internal categories
(`app/services/enrichment/taxonomy.py`: `dining, groceries, travel, transport, shopping,
bills, entertainment, health, income, other`) at the ingest boundary, so downstream
consumers never see a vendor label. Unknown/empty labels map to `other` (never silently
propagated). **Shipped** (both Plaid and CSV paths route through the enrichment hook).

### FR2 — Per-category spend
The profile reports, per category, the **average monthly dollars** spent over the
lookback window, plus overall `avg_monthly_spend`. **Shipped** (`category_breakdown`).

### FR3 — Per-category frequency (the "dining frequency" metric)
The profile reports, per category, **how many times per month** the user transacts —
the literal metric `PRODUCT.md` names. **Shipped** at the API layer:
`GET /recommendations/spending-profile` (`app/api/recommendations.py:47-70`) derives
`monthly_avg_count` (= raw `category_counts` ÷ months-spanned) and `avg_per_txn` per
category and surfaces a first-class `dining` rollup. Covered by
`tests/test_recommendations_api.py::test_spending_profile_frequency_metrics`.
_Implementation note:_ the per-month normalization lives in the endpoint, not on the
stored `SpendingProfile` (which persists only raw `category_counts`). Promoting it to a
first-class profile field is a low-value nicety, **not** an unblocked-slice priority.
(Corrected after the initial draft's audit missed the endpoint.)

### FR4 — Top merchants
The profile reports the top merchants by monthly-average spend, for explainability.
**Shipped** (`top_merchants`, top 10).

### FR5 — Freshness
`get_or_refresh` returns a cached profile when nothing has changed and recomputes when
transactions change, so recommendations track reality without a manual rebuild.
**Shipped, with one known edge** — see the gap table (the cache key does not account for
the lookback window sliding forward in wall-clock time with no new transaction).

## Current implementation vs. target (the gap)

Grounded in `app/services/spending_profile.py`, `app/services/enrichment/taxonomy.py`,
and the `SpendingProfile` model (verified this run):

| Capability | Target (PRODUCT.md Phase 2) | Today | Gap |
|---|---|---|---|
| Categorization at ingest | every txn → internal category | ✅ taxonomy applied on Plaid + CSV | none |
| Per-category monthly spend | dollars/mo per category | ✅ `category_breakdown` | none |
| **Per-category frequency** | **"times/month I dine out"** | ✅ `GET /recommendations/spending-profile` exposes `monthly_avg_count` + a `dining` rollup (tested) | none (metric shipped at API; promoting to a stored profile field is optional) |
| Top merchants | explainability | ✅ `top_merchants` (top 10) | none |
| Freshness | recompute on change | ✅ `get_or_refresh` | ⚠️ FR5 edge: profile keyed on latest txn `created_at`; as the 6-month window slides, an aged-out txn does not trigger recompute until the next ingest (bounded, self-healing) |
| Recurring vs one-off | (implied by "habits") | ❌ none | subscriptions/bills inflate discretionary category totals; not separated — see Open Q3 |
| Trend / direction | (not stated) | ❌ none | is dining rising or falling? — see Open Q2 |

**Net:** categorization, per-category *spend*, and per-category *frequency* (the owner's
literal headline) are all done and correct — the frequency metric ships via
`GET /recommendations/spending-profile`. The remaining genuinely-unshipped, unblocked
slice is the **FR5 freshness edge** (window-slide recompute, filed as **#60**). Recurring
detection and trend are candidate slices pending owner scope.

## Success criteria

- For a user with transactions, the profile reports dining (and every category) as both
  monthly spend **and** times-per-month, over a documented lookback window.
- Moving a transaction between categories moves the corresponding spend and frequency in
  the expected direction (unit test with fixtures, no DB required for the pure math).
- Newly-ingested transactions are reflected on the next `get_or_refresh` without a manual
  rebuild.
- All additive: existing `SpendingProfile` consumers (the recommendation engine) keep
  working unchanged; new fields are additive.

## Open questions (QUESTIONS FOR HUMAN)

1. **Frequency definition (FR3):** should "times per month I dine out" count **every
   dining transaction**, or **distinct dining days** (three coffees in one day = 1
   outing, not 3)? Distinct-days matches the intuitive "how often do I go out" reading;
   per-transaction is simpler and already half-built. Recommendation: **per-transaction
   for the first slice** (it's what `category_counts` already captures), with
   distinct-days as a fast-follow if the number feels inflated — but confirm.
2. **Trend / recency weighting:** is a single 6-month flat average the right horizon for
   "habits," or do you want recent months weighted more heavily / a rising-vs-falling
   signal per category? (Non-blocking; affects whether "trend" becomes a slice.)
3. **Recurring vs. discretionary:** should Phase 2 separate recurring charges
   (subscriptions, rent, fixed bills) from discretionary spend, so "dining habit"
   reflects genuine discretionary behavior rather than a fixed monthly line? This is a
   real modeling decision with card-recommendation implications (you can't change the
   card you pay rent with as freely as where you eat). Defer, or in-scope for Phase 2?

## Proposed decomposition (Stage 1 — the unblocked path)

Filable now, in priority order; **none depend on the #38 card-data decision**:

1. **Freshness edge (FR5) — filed as #60, the next unblocked slice.** Recompute when the
   lookback window has advanced past the cached window even absent a new transaction. Pure
   correctness; no new product decision.
2. **~~Per-month category frequency (FR3)~~ — ALREADY SHIPPED** via
   `GET /recommendations/spending-profile` (`monthly_avg_count` + `dining` rollup, tested).
   Only a low-value nicety remains (promote from ad-hoc endpoint math to a stored profile
   field); not prioritized. Open Q1 (per-transaction vs distinct-days) still applies if the
   frequency definition is ever revisited.
3. **Category trend signal** — *pending Open Q2.*
4. **Recurring-charge detection** — *pending Open Q3.*

Ref: `docs/prd/PRODUCT.md` (Phase 2, Success criteria), `docs/prd/recommendation-engine.md`
(consumer of this profile; its category-aware earn is separately blocked by #38).
