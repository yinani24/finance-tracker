# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Next-card recommendation showed the dollar sign-up bonus as "pts" (#196).**
  On Recommendations → **Next Card**, the bonus was rendered
  `{bonus_value.toLocaleString()} pts`, but `bonus_value` is a USD amount
  (`card_recommendation.py`: *"bonus_value = dollar value of the chosen offer …
  points/miles at `points_value_cents` per point"*), so a $600 cash bonus
  displayed as "600 pts" — and contradicted the same card's `explanation` string,
  which already prints the correct dollar value. This undercut #192 (which fixed
  the backend to value points at cents). The bonus now renders via
  `formatCurrency`. The adjacent "Score" figure — also dollar-denominated
  (`score = bonus_value + ongoing_value − first_year_fee + credit_value`) — is now
  shown as currency and relabeled "1st-yr value", matching the Portfolio/Spending
  tabs (which already use `formatCurrency`) and PRD FR4's "you'd earn ~$X" framing.
  Frontend-only; no backend/schema change.
- **Explore cards page rendered zero results (#123 regression).** The web
  `CardBonusSearchResult` type and the `/explore` page read the card page window
  from `data.cards`, but the `GET /card-bonuses` endpoint returns it under
  `results` (the tested HTTP contract — see `tests/test_card_bonuses.py`). At
  runtime `data.cards` was always `undefined`, so the page showed a real total in
  its header ("Browse N cards") yet "No cards match your filters" in the grid for
  every query. Aligned the type and page to `results`; no backend change.

### Added
- **Per-category "best held card" assignment in the portfolio recommendation
  (#177).** `GET /recommendations/portfolio` now returns an additive
  `category_assignments` field answering PRD User Story 2 — *which of your cards
  should you reach for per category* (e.g. "Use Amex Gold for dining — 4% vs 1% on
  your other cards"). For every internal category the user actually spends in, the
  engine picks the held card with the highest curated per-category earn, using the
  **same** rate lookup as the first-year earn model: a new shared
  `CardRecommendationService._category_rate` is now the single source of truth for
  both `_ongoing_value` and the new `best_card_per_category`, so the two can't
  drift. Ties resolve deterministically (highest rate → lowest annual fee →
  case-insensitive name) to keep the inputs-hash snapshot cache stable. The
  portfolio snapshot now caches the per-card analyses and the assignments as one
  blob so both survive a cache hit — the cache-hit and cold paths share a single
  `_shape_payload` helper (with a defensive wrap for legacy list-shaped snapshots)
  so a stored blob is never double-nested under `cards`. `analyze_portfolio` keeps
  its `List[dict]` contract, so the `card_insight_engine` caller is unchanged.
  Backend-only + additive; frontend rendering of the assignments is a fast-follow.
- **"Add to my wallet" from the Explore card detail page (#174).** The per-card
  detail view (`/explore/{cardId}`) now has an "Add to my wallet" action that
  creates the card via `POST /cards`, storing `name` and `issuer` **verbatim from
  the catalog dataset**. That matters beyond convenience: the recommendation engine
  matches held cards to the dataset by `name.lower()|issuer.upper()`
  (`card_recommendation.py`), so a card added this way is recognized by the
  portfolio analysis (which the freeform manual add — no issuer field — usually
  isn't). The button de-dupes against the existing wallet (name match, case-
  insensitive) and renders a disabled "In your wallet" state instead of allowing a
  duplicate; on success it invalidates both `["cards"]` and `["recommendations"]`.
  Adds `issuer` to the web `Card` type (the backend already returns it). Frontend
  only; backend untouched. Fast-follow of #123, builds on #168/#169.
- **Per-card detail page in the web UI (#168).** Clicking a card on `/explore`
  now opens an in-app detail view (`/explore/{cardId}`) that consumes the
  previously UI-less `GET /card-bonuses/{card_id}` endpoint — showing the card's
  annual fee (and first-year waiver), base earn rate, all sign-up offers (bonus
  value + spend requirement), credits/perks, and a link to the official card
  page. Unknown card ids render a clean "Card not found" (endpoint 404). Adds
  `getCardBonus(cardId)` to the web API client; grid tiles now link to the
  detail page (the external issuer link moved onto the detail view).
- **Card-catalog browse page in the web UI (#123).** A new nav-linked "Explore
  cards" page (`/explore`) renders the previously UI-less `GET /card-bonuses`
  surface: a search box plus issuer / network / max-annual-fee / personal-vs-business
  filters over the public 179-card dataset, with server-side pagination. The issuer
  dropdown is populated by a new `getCardBonusIssuers()` client fn wired to
  `GET /card-bonuses/issuers`. Each result card shows name, issuer, network, annual
  fee (flagging first-year waivers), and its best sign-up offer (highest total bonus
  value with the spend/time requirement). Loading, empty, and error states render
  gracefully. Read-only surface — no mutations, backend untouched. This makes step 3
  of the MVP loop (match against the card dataset) directly explorable, complementing
  the Recommendations page's single best pick. "Add to wallet" and a per-card detail
  page are deferred fast-follows. Ref: `docs/prd/PRODUCT.md` (MVP loop step 3),
  `docs/prd/recommendation-engine.md`.
- **Per-row error reporting on CSV import (#149).** The `POST /imports` response
  now returns an `errors[]` list — each entry `{row, reason}` naming the 1-based
  file line (header is line 1) and why it couldn't be parsed (e.g. `row 14:
  unrecognized date format: 'bogus'`) — instead of only a `skipped` count.
  `parse_csv` now returns `(rows, errors)` and `ImportResult`/`ImportSummary`
  carry the list (`len(errors) == skipped`, which is retained for back-compat).
  The Transactions "Import CSV statement" card shows a collapsible "Show N
  unparseable rows" detail listing each failed row and reason, so the user can
  fix and re-upload rather than guessing which lines were dropped. Closes the
  last unmet acceptance criterion on the CSV-ingest path. Ref:
  `docs/prd/PRODUCT.md` (data ingestion).
- **Category-aware ongoing earn in the recommendation engine (#38).** The engine
  now ranks cards by how well their per-category reward rates match *how the user
  actually spends* (dining first) — the core product premise — instead of a single
  flat cashback rate. A new curated, owner-approved data file
  `apps/api/app/data/card_category_rates.json` (path **A** from #38) maps the
  sibling dataset's `cardId` → per-category earn rate (percent-equivalent) for a
  seed of ~13 top dining/grocery/travel cards (Amex Gold, Chase Sapphire, Cap One
  Savor, Citi Strata Premier, Blue Cash, …); the upstream `credit-card-bonuses-api`
  export has no per-category rates and can't be enriched. The shared
  `_ongoing_value` seam (used by both apply-for-new and held-card analysis)
  computes earn as `Σ_category (category_monthly × 12 × rate/100)`, falling back to
  each card's flat `universalCashbackPercent` for any category — and any card — not
  in the table. **Strictly additive:** an uncurated card's score is byte-identical
  to the old flat model. Recommendation rationales now show the blended effective
  rate. See `apps/api/app/data/README.md` for the rate provenance/refresh notes.
  Ref: `docs/prd/recommendation-engine.md` (slice 3, FR1), `docs/prd/PRODUCT.md`
  (Phase 4).
- **CSV statement import in the web UI (#114).** A new "Import CSV statement"
  card on the Transactions page surfaces the previously UI-less `/imports`
  backend: pick an account, choose a `.csv` bank/card export, and upload it. The
  backend (`POST /imports`) parses, dedupes, and creates transactions, and the UI
  shows a per-run summary (added / duplicates skipped / unparseable rows) plus a
  "Recent imports" list from `GET /imports`. On success the `transactions`,
  `accounts`, `recommendations`, `spending-profile`, `insights`, and
  `insights-summary` queries are invalidated so the spending profile and card
  recommendations reflect the new data immediately. This is the keys-free path to
  get real transaction history in (Plaid needs live linking) — feeding the whole
  spending→recommendation loop. Also: `fetchWithAuth` now omits the JSON
  `Content-Type` for `FormData` bodies so the browser sets the multipart boundary.
  Consumer-side only; backend unchanged (was already shipped + mounted, just
  unreachable). Ref: `docs/prd/spending-intelligence.md`, `docs/prd/PRODUCT.md`
  (MVP loop step 1: connect/ingest accounts).
- **Spending Profile view in the web app (#106).** A new "Spending Profile" tab on the
  Recommendations page renders `/recommendations/spending-profile`: per-category monthly
  averages (dining first) as ranked bars, the headline "you dine out ~N×/month" figure
  (`dining.monthly_avg_count`) with avg-per-visit, monthly txn counts and avg-per-transaction
  per category, and top merchants. Includes loading and empty states ("Add or sync
  transactions to see your spending profile"). Previously the backend computed this profile
  but no UI rendered it. Also updated the web `SpendingProfile`/`CategorySpend` types to match
  the current API response (`count`, `monthly_avg_count`, `avg_per_txn`, top-level `dining`).
  Ref: `docs/prd/spending-intelligence.md` (User stories 1–2, FR3).
- **Edit & delete manually-added cards in the web UI (#118).** Each card in the
  "Added manually" section of the Cards page now has an **Edit** action (a dialog
  prefilled with name / network / annual fee, mirroring the Add-Card form) and a
  **Delete** action (inline confirm). Edits PATCH `/cards/{id}` via a new
  `updateCard` client fn; deletes use the already-shipped-but-unwired `deleteCard`.
  On success the `cards` and `recommendations` queries are invalidated so the
  recommendation engine's existing-card math (earn rates, first-year-value net of
  annual fee) re-runs. Previously a manual card could only be created — a typo in
  the name, a wrong fee, or a wrong network was permanent. Plaid-linked cards stay
  read-only. Consumer-side only; no card-catalog data. Ref:
  `docs/prd/recommendation-engine.md`.
- **Inline transaction recategorization in the web UI (#109).** The transactions page
  now renders an editable category `<select>` (options = the fixed internal taxonomy:
  `dining, groceries, travel, transport, shopping, bills, entertainment, health, income,
  other`) on each row instead of a read-only badge. Changing it PATCHes
  `/transactions/{id}` via a new `updateTransaction` client fn; on success the
  `transactions`, `recommendations`, `insights`, and `insights-summary` queries are
  invalidated so the spending profile self-corrects (the backend already fires
  `TRANSACTION_MUTATED` to recompute). Closes the write side of the spending-intelligence
  loop opened on the read side by #106 — a mis-categorized transaction (e.g. a restaurant
  mislabeled `other`) can now be fixed from the UI. Consumer-side only; per-row loading
  (disabled while saving) and an error banner included.

### Changed
- **Cleared the remaining ruff debt in `apps/api/tests/` + `alembic/` (#80).** With `app/`
  already clean (#74), this clears the last 53 errors so `ruff check .` is green repo-wide —
  the precondition for a lint-in-CI gate (#72 Q2). 15 import issues auto-fixed
  (`I001`/`F401`) and 38 over-length lines (`E501`) wrapped, across 11 test modules and 3
  autogenerated migrations. Lint-only: test edits are line-wrapping/import-ordering with no
  behavior change, and the migration edits touch only imports/formatting — no schema
  operation, revision id, or `down_revision` altered. Verified: `ruff check .` passes and all
  235 tests still collect. Ref: #74 (`app/` slice), #72 (lint-gate follow-up).
- **Made hand-written `apps/api/app/` source ruff-clean (#74).** `ruff check .` reported
  65 errors on `main`; the 12 in the production source (`app/`) are now cleared — 3 dead
  imports removed (`sqlalchemy.func` in `repositories/insight.py`; `typing.Optional` and
  the unused `Insight` model in `services/insight_dispatcher.py`, all confirmed
  unreferenced) and 9 over-length lines wrapped. `ruff check app/` is now clean, so a lint
  gate can start green at the source layer. Lint-only — no logic or behavior change; the
  `tests/` and autogenerated `alembic/versions/` debt is deferred to a follow-up slice.
  Ref: #72 (lint-gate follow-up).

### Added
- **`apps/api/scripts/setup-test-db.sh`** — boots a disposable local Postgres and
  provisions the `finance_tracker_test` DB (and login role) the conftest fixtures
  expect, so the full test suite runs in an ephemeral sandbox with no external
  service DB. Idempotent; data lives under a throwaway `$PGDATA`.

### Changed
- **Capped API dependency upper bounds (#68).** Every runtime and dev dependency in
  `apps/api/pyproject.toml` declared an unbounded `>=` lower bound with no lockfile, so
  a fresh `pip install -e ".[dev]"` could silently pull a breaking major and two installs
  on different days could diverge. Added compatible-release upper bounds (major-version
  caps; `<0.1` for `python-multipart`, `<41.0` for `plaid-python`). The known-good
  resolution that passes all 235 tests today falls inside every new range — verified
  in-sandbox by reinstalling under the caps and re-running the full suite. No source or
  behavior change.
- **Stopped tracking generated `apps/api/finance_tracker_api.egg-info/` build
  artifacts.** The root `.gitignore` already declared `*.egg-info/`, but the
  directory had been committed before that rule existed, so every implementer
  who ran `pip install -e` regenerated it and dragged the artifacts into their
  diff (e.g. PR #62 carried 3 egg-info files among 7 changed). `git rm --cached`
  aligns the repo with its own ignore rule; no source or behavior change.

### Documentation
- **Documented the in-sandbox test recipe in `CLAUDE.md` (#68).** `uv` builds the
  `plaid-python` sdist cleanly where the sandbox's system `pip`/`setuptools` fails, and
  the new helper script supplies Postgres. Together they run the full `pytest` suite (235
  tests) rather than the `--noconftest` pure-function subset earlier runs were limited to.
- **Reconciled `docs/prd/recommendation-engine.md` with shipped code.** The PRD predated
  two merged slices and still described them as unbuilt: dollar-valued sign-up bonuses
  (cents-per-point, #28) and the flat first-year ongoing-rewards term (#37). Corrected the
  gap table, FR1, the "bottom line", and the decomposition to mark slices 1–2 SHIPPED;
  downgraded Open Question 1 from a blocking "bonuses are in points, must fix" bug to a
  resolved, live-and-flagged 1.0¢/point default (owner may still override). The sole
  remaining engine gap — category-aware earn (slice 3) — stays correctly blocked on #38.
  No source or behavior change.
- **Added `docs/prd/spending-intelligence.md`** — the Phase-2 PRD, which had never
  been captured. Documents the shipped baseline (ingest-time categorization +
  per-category monthly spend, top merchants, freshness) against the `PRODUCT.md`
  Phase-2 promise and proposes an unblocked Stage-1 decomposition. All slices are
  consumer-side and independent of the card-data decision blocking #38.
- **Corrected the PRD's FR3 status: the per-month dining-frequency metric is already
  shipped** via `GET /recommendations/spending-profile` (`monthly_avg_count` + `dining`
  rollup, covered by `test_spending_profile_frequency_metrics`). The initial draft's
  audit missed the endpoint. The next unblocked slice is the FR5 freshness edge
  (window-slide recompute), filed as #60.

### Fixed
- **Spending profiles now recompute when the lookback window slides into a new
  month, even without a new transaction.** `get_or_refresh` previously only
  recomputed when a newer transaction existed, so a user who stopped syncing kept
  getting the old profile while aged-out months silently inflated the averages
  (dining $/mo, `monthly_avg_count`) — and skewed the recommendation inputs.
  It now detects that the current 6-month cutoff has advanced past the cached
  profile's earliest transaction (`period_start`) and recomputes. The same-window
  cache-hit path is unchanged. A `today` param was added to
  `_lookback_start`/`compute_profile`/`get_or_refresh` (defaults to `date.today()`,
  additive) so the slide can be tested hermetically. (#60)
- **"Apply for a new card" recommendations no longer drop cards whose top offer
  tier is out of reach when a smaller tier is achievable.** `recommend_next_card`
  selected each card's single highest-dollar-value offer with `_best_offer` and
  *only then* checked achievability, so a card advertising two concurrent offers —
  a high-spend/high-bonus tier plus a low-spend/low-bonus tier — was dropped
  entirely for any user who couldn't hit the top tier, even when they could
  comfortably earn the smaller one. This hit **27 of the 179 dataset cards (15%)**
  (e.g. Delta SkyMiles Gold: 90k pts @ $5,000/180d *or* 50k pts @ $2,000/180d) and
  disproportionately penalized the lower-spend users the achievability filter is
  meant to serve. The engine now picks the **best _achievable_ offer** per card
  (`_best_achievable_offer`): it filters to the tiers the user can reach, then
  takes the highest-valued of those; a card is skipped only when *no* tier is
  achievable. Single-offer cards are unaffected. (#55)
- **Groceries are now split from dining at ingest.** Plaid's
  `personal_finance_category.**primary**` value `FOOD_AND_DRINK` covers *both*
  restaurants and groceries, so all grocery spend was folding into `dining` —
  inflating the exact dining-share signal the dining-first recommender ranks on
  and leaving the taxonomy's `groceries` bucket permanently empty. `plaid_service`
  now derives the category from `personal_finance_category.**detailed**` for food
  transactions (`FOOD_AND_DRINK_GROCERIES` → `groceries`;
  `_RESTAURANT`/`_COFFEE`/`_FAST_FOOD`/`_BEER_WINE_AND_LIQUOR`/… → `dining`),
  falling back to `primary` when `detailed` is absent (no regression for older
  data). Non-food primaries keep using `primary` unchanged — their detailed
  labels aren't in the taxonomy and would wrongly collapse to `other`. (#52)
- **Transaction categories are now mapped into the internal taxonomy at ingest.**
  The vendor-agnostic boundary (`taxonomy.map_to_internal`) existed and was
  unit-tested but was **never called in the pipeline**: the default `NoopProvider`
  echoed Plaid's raw label back, so `category_breakdown` was keyed on raw strings
  like `"food and drink"`/`"general merchandise"` instead of the internal set
  (`"dining"`/`"shopping"`). That broke the provider contract in `base.py` and
  would have silently zeroed the category signal for the upcoming category-aware
  recommendation engine (which keys on `"dining"`). `NoopProvider` now maps
  `plaid_category` through `map_to_internal`, preserving the raw label in
  `raw_provider_category`. A `None` upstream category still passes through as
  `None` (no overwrite), so the statement-import path is unchanged, and the
  provider-failure fail-open path still keeps the raw Plaid value. (#51)
- **Recommendation snapshots now refresh when the card dataset changes.** The
  cached `next-card` / `portfolio` results were keyed only on the user's
  spending profile and the cards they own — not on the card **dataset** the
  recommendations are actually ranked over, nor the point valuation. So after an
  upstream sign-up-bonus change, a newly added card, or a discontinuation
  (exactly the churn PRD FR5 *Freshness* covers), the GET endpoints kept serving
  the old ranking until the user changed their profile/cards or manually POSTed
  `/refresh`. The cache key now includes a fingerprint of the dataset and
  `points_value_cents`, so the next read recomputes automatically. The dataset
  fetch is a process-wide TTL cache, so this adds no upstream round-trip on the
  cache-hit path. Recommendation outputs are otherwise unchanged. (#47)
- **Wallet analysis (`analyze_portfolio`) no longer suggests discontinued or
  already-owned cards as alternatives.** When a held card is flagged
  underperforming, the engine proposes better-net-value alternatives — but the
  loop excluded only the exact card being analyzed, so it could recommend
  "switch to" a **discontinued** card (3 attractive $0-fee ones exist in the
  dataset — US Bank Altitude Reserve/Smartly at 2%, Amex Everyday) or a card the
  user **already holds**. It now skips `discontinued` cards and any card in
  `user_cards`, matching the exclusions `recommend_next_card` already enforces.
  Otherwise-eligible alternatives are unaffected. (#44)
- **First-year fee waiver now honored in the "apply for a new card" recommendation**
  (`recommend_next_card`). The ranking objective is *total first-year value*, but the
  score subtracted a card's full listed `annualFee` even when the card waives that fee
  the first year (`isAnnualFeeWaived`). This understated the first-year value of the 13
  waived-fee cards in the dataset by $79–$150 each, so they could be ranked below cards
  that actually cost more in year one. A shared `_first_year_fee(card)` helper now
  returns `$0` when `isAnnualFeeWaived` is set, and the score/explanation use it (the
  explanation notes `"$X waived year 1"`). `analyze_portfolio` intentionally keeps the
  full recurring `annualFee` — it judges whether a *held* card is worth keeping in
  steady state, where the fee recurs every year. Score for non-waived cards is
  unchanged. (#41)

### Added
- **First-year ongoing-rewards term in the "apply for a new card" recommendation**
  (`recommend_next_card`). The score now models real earn — `bonus + ongoing −
  fee + credits` — where `ongoing = avg_monthly_spend × 12 × universalCashbackPercent`
  (flat cashback). Previously a card was ranked on its sign-up bonus, credits, and
  fee alone, so a strong everyday-earn no-fee card could lose to a bonus-heavy fee
  card even when it delivered far more first-year value. Each result now exposes an
  `ongoing_value` component (additive; existing keys unchanged) and the explanation
  string surfaces all four value components (bonus / ongoing / credits / fee). The
  flat-earn calc is now a shared `_ongoing_value` helper used by both
  `recommend_next_card` and `analyze_portfolio`, so the two modes can't drift.
  Category-aware earn (per `category_breakdown`) remains a future slice. (#35)
- **Manual CSV bank-statement import (Plaid-free ingest path)** — `POST /imports`
  accepts a multipart CSV upload plus an `account_id`, stores the file, and parses
  single-signed-amount rows (tolerant date/`$`/comma/parenthesis handling) into
  deduplicated `Transaction`s (`source="import"`) under that account. Imported rows
  flow through the same dedupe fingerprint and enrichment hook as Plaid sync, so
  they categorize identically. Re-uploading a statement adds nothing (idempotent);
  unparseable rows are skipped and counted; a bad/empty/non-CSV file records the
  import as `failed` and returns 400 with no partial rows. `GET /imports` and
  `GET /imports/{id}` report status + imported-transaction count. New
  `FT_IMPORT_STORAGE_DIR` (local dev storage). Amount sign convention (negative =
  spend) is documented and flagged for owner confirmation. (#22, slice 1)
- Shared `app/services/dedupe.py` and `app/services/enrichment/apply.py` extract the
  transaction dedupe-hash and enrichment-apply logic so the Plaid and import ingest
  paths cannot drift; `plaid_service` now delegates to both (behavior unchanged).

### Changed
- Sign-up-bonus value in the recommendation engine (`recommend_next_card`) is now
  **dollar-denominated**: cashback (`currency == "USD"`) bonuses count at face value
  and points/miles convert at a configurable blended `FT_POINTS_VALUE_CENTS`
  (default 1.0¢). Previously bonuses were summed as raw point counts and mixed with
  dollar fees/credits, so a large points bonus could outrank a cashback card ~450×
  purely on point magnitude. `score`, `bonus_value`, and the explanation string are
  now all in dollars, so points and cashback cards rank on one scale (owner-confirmed
  "total first-year value" objective). `_best_offer` ranks by the same USD valuation
  for consistency. Response keys are unchanged (behavioral/valuation only).

### Fixed
- **Broken Alembic migration chain on `main`** — migration `72bfe64b241f`
  (spending_profiles / recommendation_snapshots / `cards.issuer`) declared
  `down_revision = '24568b8e4f03'`, a phantom revision that was never committed
  anywhere in history, splitting the version graph into two disconnected chains
  and making `alembic upgrade head` fail outright. Repointed its `down_revision`
  to the real predecessor at creation time, `0b62d248f5e8`, restoring a single
  linear chain (`001 → 0b62d248f5e8 → 72bfe64b241f → 14fc7f6a99e3`). No schema
  or DDL change — history-metadata only. Unblocks all migration-bearing work
  (e.g. #23/#25, #24).

### Documentation
- Added `docs/prd/recommendation-engine.md` (Phases 4–5 PRD). Documents the
  owner-confirmed "total first-year value" objective and reconciles it against the
  existing `card_recommendation.py` engine, flagging the gap: ongoing category-aware
  rewards (half the objective, and the reason we read dining habits) are not yet
  modeled, and bonus points are summed without a cents-per-point valuation. Includes
  open questions and a proposed Stage-1 decomposition.

### Added
- **Per-category transaction-frequency metrics** in the spending profile — the
  Phase-2 "how many times did I dine out" signal. `compute_profile` now records a
  per-category transaction **count** (persisted in a new `category_counts_json`
  column, added by Alembic migration `a1b2c3d4e5f6`), accumulated in the existing
  single pass over transactions. `GET /recommendations/spending-profile` extends
  each `categories[]` entry with `count`, `monthly_avg_count`, and `avg_per_txn`
  (average ticket size), and adds a top-level `dining` rollup (null when absent).
  Additive and non-breaking — existing response keys are unchanged.
- Provider-swappable **transaction-enrichment layer** (`app/services/enrichment/`)
  over stored Plaid transactions. `sync_transactions` now runs newly-added rows
  through the configured `EnrichmentProvider` and overwrites `category` /
  `normalized_merchant` from the result. The default `noop` provider echoes the
  raw Plaid values back unchanged, so behavior is identical until a real provider
  is configured via `FT_ENRICHMENT_PROVIDER`. Enrichment is fail-open — a provider
  error or mismatched batch is logged and the raw Plaid category is kept, so
  ingest never breaks. Ships a fixed internal category taxonomy
  (`dining, groceries, travel, transport, shopping, bills, entertainment, health,
  income, other`) with a `map_to_internal` mapper for wiring real providers next.
- OAuth institution support for Plaid Link (Chase, Bank of America, Wells Fargo,
  Capital One, …). `create_link_token` now sends a `redirect_uri` when
  `FT_PLAID_REDIRECT_URI` is configured, and the web `PlaidLinkButton` completes
  the OAuth round-trip (persists the link token across the redirect, passes
  `receivedRedirectUri`, and re-opens Link on return). Without this, selecting an
  OAuth bank failed in Link with a generic error; non-OAuth sandbox banks are
  unaffected (no `redirect_uri` sent when the setting is blank). The redirect URI
  must also be registered in the Plaid Dashboard — see `.env.example`.
- Plaid API errors are now mapped to meaningful HTTP responses instead of unhandled 500s: re-link conditions (`ITEM_LOGIN_REQUIRED`, `INVALID_ACCESS_TOKEN`, …) → **409** with `{"error_code", "action": "relink"}`; transient/rate-limit conditions → **503** with `action: "retry"`; other Plaid failures → **502**. Access tokens and raw Plaid error internals (`error_message`, `request_id`) are never surfaced in responses or logs.

### Fixed
- Restored missing `app/services/card_bonuses.py` service module. Its absence made
  `app/api/card_bonuses.py` and `app/services/recommendation_snapshot.py` fail to
  import, which broke `app.main` startup and the entire test suite.
- `card_insight_engine` no longer fetches card data from the third-party
  `andenacitelli/credit-card-bonuses-api` fork; all card data now resolves to the
  sibling `yinani24/credit-card-bonuses-api` via the `card_bonuses` service, so the
  insight engine and the recommendation/snapshot paths can no longer disagree about
  the card landscape.

### Added
- `POST /plaid/webhook` — event-driven transaction sync. On a
  `TRANSACTIONS / SYNC_UPDATES_AVAILABLE` webhook it looks up the `PlaidItem` by
  Plaid's `item_id`, runs `sync_transactions`, and fires the `TRANSACTIONS_SYNCED`
  insights event (mirroring the manual sync path). Unhandled webhook types and
  unknown items are accepted with a 200 no-op, and sync failures return 200 (not
  5xx) to avoid Plaid retry storms. Verification is behind a `verify_webhook`
  stub (real Plaid-Verification JWT check lands with #8).
- `POST /plaid/webhook` now verifies the `Plaid-Verification` JWT (ES256): the
  signature is checked against the key from `/webhook_verification_key/get`
  (cached by `kid`, so no per-request fetch), the `alg` is pinned to `ES256`
  (rejecting `alg=none`/HS256 confusion), the `iat` must be within a 5-minute
  replay window, and the `request_body_sha256` claim is compared constant-time
  against the raw request body. Invalid/missing/tampered requests get **401**.
  Verification defaults on and can be disabled for local/sandbox testing via
  `FT_PLAID_WEBHOOK_VERIFY=false`.
- `FT_PLAID_WEBHOOK_URL` config — when set, registered as the `webhook` on
  `LinkTokenCreateRequest` so Plaid knows where to deliver callbacks.
- `card_bonuses.fetch_cards_sync()` — a synchronous fetch that shares the same
  process-wide cache (and `FT_CARD_BONUSES_URL` override) as the async path, giving
  sync consumers a single source of truth for card data.
- `card_bonuses` service: cached fetch of the sibling credit-card-bonuses-api export
  with search/filter/pagination, issuer listing, and card lookup by id. Serves stale
  cache on upstream failure and raises `CardBonusesError` only on a cold cache.
- `FT_CARD_BONUSES_URL` config override for the card-bonuses data source.
- Test coverage for the card-bonuses service and `/card-bonuses` API router.

### Changed
- Consolidated card-data fetching: `card_insight_engine.fetch_card_bonuses` and
  `recommendation_snapshot._fetch_cards` now delegate to `card_bonuses.fetch_cards_sync`,
  sharing one upstream URL and one process-wide cache instead of three separate caches
  pointed at two different upstreams.
- Removed legacy CLI app (core/, importers/, dashboard/, scripts/, templates/, tests/, main.py)
- Removed old config files (pyproject.toml, pytest.ini, .coveragerc, requirements.txt, .pre-commit-config.yaml, config.json)
- Removed old docs/ directory
- Updated .gitignore, README.md, CLAUDE.md for new apps/ structure

### Added
- Insights substrate: unified `Insight` model + scoring/ranking framework with pluggable engines
- `InsightDispatcher` with dismiss-sticky resurface logic (90 day / 25% impact threshold)
- `/insights` API endpoints (list, summary, history, get, dismiss, snooze, acted-on, mark-seen, refresh)
- `CardInsightEngine` adapter migrating card recommendations onto the substrate
- Event fires for insights on transaction, goal, card, and Plaid sync mutations
- `/insights` page with engine tabs, expandable detail panels, and lifecycle actions
- Dashboard insights widget showing top 3 active insights
- Sidebar nav entry for Insights
- Credit card recommendation engine with sign-up bonus achievability scoring
- Portfolio analysis to flag underperforming cards and suggest alternatives
- Spending profile aggregation service with caching and staleness detection
- `/recommendations` API endpoints (next-card, portfolio, spending-profile, refresh)
- Recommendations page with Next Card and Portfolio Analysis tabs
- Dashboard widget showing top 2 card recommendations
- `issuer` field on Card model for better card matching
- `spending_profiles` and `recommendation_snapshots` database tables
- FastAPI backend (`apps/api/`) with PostgreSQL, Supabase Auth, Alembic migrations
- CRUD endpoints for accounts, transactions, goals, cards
- Plaid integration endpoint
- Next.js frontend (`apps/web/`) with TypeScript and Tailwind
- Google and Apple OAuth sign-in on login and signup pages
- Split-screen auth layout with branding panel
- Password visibility toggle and strength indicators on signup
- Forgot password link on login page
