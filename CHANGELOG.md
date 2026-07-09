# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
