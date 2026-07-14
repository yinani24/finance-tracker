# `app/data/` — curated static datasets

Small, maintained-in-repo reference data the recommendation engine needs but the
upstream card dataset does not provide.

## `card_category_rates.json`

**Why it exists.** The sibling `credit-card-bonuses-api` export (the source of
truth for card metadata and sign-up bonuses) carries only a single flat
`universalCashbackPercent` per card — it has **no per-category earn rates**
(verified in the research on issue #38: 179 cards, no `categories`/`multipliers`/
`rewardRates` field; and that repo is a read-only mirror that "will not accept
pull requests," so it can't be enriched upstream). But the product's core promise
— *"because you dine out a lot, use **this** card"* — needs category-aware earn.
This file is the owner-approved (issue #38, path **A**) in-repo bridge.

**Shape.** Top-level keys are the upstream `cardId`. Each value maps one or more of
the 10 internal spending categories (`app/services/enrichment/taxonomy.py`:
`dining, groceries, travel, transport, shopping, bills, entertainment, health,
income, other`) to an earn rate. The `_meta` block (and any per-card `_name`)
are documentation, ignored by the loader.

**Unit — percent-equivalent.** A rate is comparable to a card's flat
`universalCashbackPercent`: a card earning *4x points on dining* is `"dining": 4`.
For points cards (Amex MR, Chase UR, Citi TY, Cap One miles) this is the **raw
multiplier**, which is *conservative* — transferable points often redeem above
1.0¢, but ongoing earn is not yet scaled by `points_value_cents` (that knob
currently applies only to sign-up bonuses).

**Fallback / additivity.** `card_recommendation.py` loads this once at import.
For any category a card omits here — and for **every card not listed** — earn
falls back to that card's flat `universalCashbackPercent`. So adding this file
never changes the score of an uncurated card, and only *refines* the curated ones.

**Scope of this first slice (intentionally not modeled).** Rotating 5% categories
(Discover It, Citi Custom Cash), portal-only elevated rates (e.g. Venture X
5x/10x through the Capital One travel portal), and per-category annual spend caps
(e.g. Blue Cash Preferred's $6k US-supermarket cap) are **not** encoded — the
base direct-spend multiplier is used. These are candidate follow-ups.

### Refresh / provenance

- **`as_of`** in `_meta` marks the curation date. Reward schedules change; re-verify
  periodically (the same cadence sign-up bonuses already need eyeballing).
- Rates are drawn from public issuer reward schedules and are **agent-curated,
  pending owner verification**. Correct a rate by editing the card's entry; add a
  card by adding its `cardId` block. No code change needed — the engine picks it up
  at next import.
- To find a `cardId`, look it up by name in the upstream export
  (`https://raw.githubusercontent.com/yinani24/credit-card-bonuses-api/master/exports/data.json`).
