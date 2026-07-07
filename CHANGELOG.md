# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
