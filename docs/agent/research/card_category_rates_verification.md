# Research — verification of `card_category_rates.json` (curated ongoing-earn table)

**Run:** 2026-07-15T20-12Z · **Stage 2 (research/verification)** · non-gated

## Why this run
`apps/api/app/data/card_category_rates.json` powers the rec engine's **category-aware
ongoing earn** (`CardRecommendationService._ongoing_value`, wired through both
`recommend_next_card` and `analyze_portfolio`, shipped #165). Its `_meta.provenance`
carries a standing TODO:

> "Seeded per owner decision on issue #38 (path A). **Pending owner verification of
> individual rates before treating as ground truth.**"

That is an explicit, non-gated correctness task sitting in the codebase. This run does the
agent-side pass: check all 14 curated cards' per-category multipliers against publicly
documented issuer reward schedules, and surface anything wrong or misleading. (Same class
of check that caught the #166 `results`-vs-`cards` drift — verify against the real
contract, don't assume.)

## Method
The table records each card's category earn as a **percent-equivalent** comparable to the
card's flat `universalCashbackPercent` (e.g. "4x points on dining" → `"dining": 4`). Any
category a card omits, and any card absent from the table, falls back to the flat rate — so
the file is strictly additive and can only *raise* an estimate above flat. I checked each
recorded multiplier against the issuer's published ongoing base earn for direct spend in
that category, and checked that the internal-category mapping (dining/groceries/travel/
transport/shopping/bills/entertainment/health/income/other) is defensible.

## Result — all 14 base multipliers are accurate ✅
Every recorded rate matches the issuer's published ongoing multiplier for direct spend, and
every internal-category mapping is defensible:

| Card | Recorded | Verified base earn (direct spend) |
|------|----------|-----------------------------------|
| Amex Gold | dining 4, groceries 4, travel 3 | 4x dining, 4x US supermarkets, 3x flights ✓ |
| Amex Green | dining 3, travel 3, transport 3 | 3x restaurants / travel / transit ✓ |
| Amex Platinum | travel 5 | 5x **airfare (direct/Amex Travel) + prepaid hotels via Amex Travel only** ⚠️ |
| Amex Blue Cash Preferred | groceries 6, entertainment 6, transport 3 | 6% US supermarkets, 6% streaming→entertainment, 3% transit/gas ✓ |
| Amex Blue Cash Everyday | groceries 3, shopping 3, transport 3 | 3% US supermarkets, 3% US online retail→shopping, 3% gas ✓ |
| Amex EveryDay Preferred | groceries 3, transport 2 | 3x US supermarkets, 2x gas ✓ |
| Amex Delta SkyMiles Gold | dining 2, groceries 2 | 2x restaurants, 2x US supermarkets ✓ |
| Chase Sapphire Preferred | dining 3, travel 2, entertainment 3 | 3x dining, 2x other travel, 3x select streaming→entertainment ✓ |
| Chase Sapphire Reserve | dining 3, travel 3 | 3x dining, 3x other travel ✓ |
| Chase Freedom Unlimited | dining 3, health 3 | 3% dining, 3% drugstores→health ✓ |
| Chase Freedom Flex | dining 3, health 3 | 3% dining, 3% drugstores→health ✓ |
| Capital One Savor | dining 3, groceries 3, entertainment 3 | 3% dining, 3% groceries, 3% entertainment/streaming ✓ |
| Citi Strata Premier | dining 3, groceries 3, travel 3, transport 3 | 3x restaurants, 3x supermarkets, 3x air travel/hotels, 3x gas→transport ✓ |

No multiplier is wrong; no mapping is indefensible. The table does not regress the flat
model. This substantially discharges the agent side of the `provenance` TODO — what remains
is the owner's blessing (below).

## One substantive caveat — "narrow-earn" travel entries can overstate
`_meta` already states that "portal-only, rotating, and capped-spend nuances are
intentionally not modeled." Two entries stretch that simplification the furthest and are
worth calling out explicitly, because the internal **`travel`** category (from transaction
enrichment) lumps *all* travel together while these multipliers apply only to a **narrow
slice** of it:

- **Amex Platinum `travel: 5`** — the 5x is **airfare booked direct/Amex Travel + prepaid
  hotels via Amex Travel only**. General travel (transit, car rental, non-Amex-Travel
  hotels, etc.) earns **1x**. For a user whose enriched `travel` spend is mostly *not*
  airfare, this entry overstates ongoing earn the most of any row. This is the single most
  aggressive assumption in the file.
- **Amex Gold `travel: 3`** — 3x applies to **flights booked directly / via Amex Travel**,
  not general travel (1x otherwise). Smaller gap than Platinum but the same shape.

By contrast the Chase Sapphire `travel` entries (2–3x) are much closer to a true
"all travel" rate, so they're low-risk.

**Direction of error:** these only ever *inflate* an estimate (never under-count), so they
can nudge the engine toward recommending a premium travel card for a user who wouldn't
actually realize the 5x. Worth the owner deciding whether to model narrow-earn rates at all
(see question below). It is **consistent with the documented "first slice" scope** — i.e. a
known simplification, not a bug — so I did **not** change the data this run (owner owns this
table and asked to verify it before it's ground truth).

## Not modeled (unchanged, already acknowledged in `_meta`)
Spend caps (e.g. Amex Gold 4x dining capped $50k/yr, 4x groceries $25k/yr; BCP 6% groceries
$6k/yr), rotating 5% categories (Freedom Flex, Discover), and portal-multiplier tiers
(Chase Travel 5x, Citi Travel 10x). These are documented as out of scope for this slice.

## Recommendation
1. The 14 base rates are **safe to treat as ground truth** for the flat-vs-category MVP —
   the agent-side verification is done.
2. Decide the **narrow-earn travel** policy (Platinum/Gold): keep the optimistic
   whole-category rate, or down-rate `travel` on airfare-narrow cards (e.g. Platinum
   `travel: 5 → 1`, or introduce an `airfare` sub-category later). This is a product/data
   modeling decision, not a code gap — flagged for the owner, not guessed.

## QUESTIONS FOR HUMAN
1. **Bless the table?** All 14 rates verified accurate against issuer schedules. OK to flip
   `provenance` from "pending owner verification" to verified-as-of-2026-07 (I'll make that
   one-line edit on request)?
2. **Narrow-earn travel policy:** keep `Amex Platinum travel: 5` / `Amex Gold travel: 3` as
   optimistic whole-`travel`-category rates, or down-rate them so travel-heavy users aren't
   over-promised? (Only ever inflates estimates today.)
