# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
