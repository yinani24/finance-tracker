# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `pre-commit` framework with `.pre-commit-config.yaml` — replaces manual hook scripts
- Hooks: trailing-whitespace, end-of-file-fixer, check-yaml, check-json, check-merge-conflict, detect-private-key, no-commit-to-branch (main)
- `ruff` linter + formatter (replaces flake8/isort/black)
- `mypy` static type checking hook
- `bandit` security linter hook
- `pyproject.toml` with ruff, mypy, and bandit configuration

### Changed
- Reorganized codebase: `core/` (data_store, categorizer, goals), `dashboard/` (renderer, analytics), `importers/real_data.py` — `main.py` is now the sole root-level entry point
- `scripts/install_hooks.sh` now uses `pre-commit install` instead of manual hook copy
- Applied ruff formatting and import sorting across all source files

## [0.4.0] - 2026-03-26
### Added
- Config-driven account names via `config.json → import_accounts` (no card numbers in code)
- `statements_manifest.json` (gitignored) holds all statement file paths and metadata
- `statements_manifest.example.json` committed as setup template
- `scripts/check_secrets.py` pre-commit hook — blocks staged sensitive data (card patterns, statement paths, data files)
- `scripts/check_changelog.py` pre-commit hook — warns when CHANGELOG.md is not updated alongside code changes
- `scripts/pre-commit` shell script wiring both hooks in sequence
- `scripts/install_hooks.sh` one-command hook installer (`sh scripts/install_hooks.sh`)
- Comprehensive documentation: `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/CONTRIBUTING.md`
- Reference library in `docs/references/` — 7 files covering transaction schema, config schema, CLI reference, dashboard context, bank formats, health score algorithm, and testing guide
- `CHANGELOG.md` with retroactive version history
- `pytest.ini` enforcing 100% test coverage via `pytest-cov`
- Test fixtures for BofA Visa, BofA Checking, Robinhood CSV, and Robinhood PDF parsers
- Full test suite for `import_real_data.py` parsers, `check_secrets.py`, and `check_changelog.py`

### Changed
- `import_real_data.py` fully refactored: module-level global mutable state replaced by pure functions returning `(added, skipped)` tuples. Account names now read from `config.json → import_accounts`. Statement paths read from `statements_manifest.json`.
- All modules now have type hints and docstrings on every public and private function: `data_store.py`, `categorizer.py`, `goals.py`, `dashboard.py`, `dashboard_data.py`, `importers/csv_parser.py`, `importers/pdf_parser.py`, `finance.py`, `import_real_data.py`
- `finance.py`: all imports consolidated to top level; duplicate import loop extracted to private `_run_store_import()` helper
- `README.md` improved with concise quick-start, troubleshooting section, and links to full documentation

### Security
- Sensitive identifiers (partial card numbers, account-number-based names) removed from all tracked files
- `statements_manifest.json` added to `.gitignore` — statement file paths are never committed
- Pre-commit hook blocks accidental commits of card patterns, `statements/` path references, and `data/` files

## [0.3.0] - 2026-03-25
### Added
- 4-tab HTML dashboard: Overview, Spending, Goals, Insights
- Financial health score algorithm (0–100, 5 dimensions) with letter grade (A/B+/B/C/D/F)
- Actionable cuts engine — per-category and subscription spending analysis with savings recommendations
- Action plan generator linked to at-risk savings goals
- Spending percentage of income breakdown per category
- Top merchants table per calendar month
- DaisyUI + Alpine.js + Chart.js fully inlined (no CDN dependency; works offline)

## [0.2.0] - 2026-03-24
### Added
- `dashboard_data.py` data layer with `build_context()` as the single orchestrator entry point
- `compute_kpis()` — income, expenses, savings rate, net worth, month-over-month deltas
- `compute_category_trends()` — rolling category spend across configurable trailing months
- `compute_health_score()` — 5-dimension scoring: savings rate, spending trend, goal progress, subscription ratio, emergency fund
- `compute_actionable_cuts()` — identifies high-spend and fast-growing categories
- `compute_action_plan()` — generates specific savings actions tied to goals and cuts
- `compute_spending_pct_of_income()` — per-category income allocation percentages
- `compute_account_balances()` — current balance per linked account
- `compute_top_merchants()` — top 10 merchants by spend for a given month

### Changed
- `dashboard.py` refactored to thin renderer: all analytics logic moved to `dashboard_data.py`, template rendering is the only responsibility

## [0.1.0] - 2026-03-24
### Added
- CLI (`finance.py`) built with Click, with the following commands:
  - `import csv` — import a bank CSV export (Chase, BofA, Amex formats)
  - `import pdf` — import a bank PDF statement (generic table format)
  - `add` — manually add a transaction
  - `summary` — show income/expense summary for a month
  - `top-categories` — show top spending categories across trailing months
  - `spending` — show spending trend for a specific category
  - `networth` — calculate net worth from account balances
  - `account update` — update account name and balance
  - `tag` — tag a transaction as income or savings
  - `goal set` — set a monthly savings target or named goal
  - `goal status` — show progress toward all goals
  - `dashboard` — generate and open the HTML dashboard
- `DataStore` — flat-file transaction storage using append-only CSV with SHA256 deduplication (16-char hex ID)
- `Categorizer` — keyword-based auto-categorizer driven by `config.json → categories`; uses longest-match-wins strategy
- `CSVParser` — bank CSV importer with per-bank format profiles (Chase, BofA, Amex) configured via `config.json → bank_formats`
- `PDFParser` — generic table-based PDF importer using pdfplumber
- `import_real_data.py` — custom regex parsers for Chase credit, BofA Visa credit, BofA checking/savings, Robinhood CSV, and Robinhood brokerage PDF statements
- `goals.py` — savings goal management: monthly targets and named goals with deadlines, persisted in `data/goals.json`
- Integration test suite covering all CLI commands and dashboard generation
- `config.json` — central configuration for categories, bank CSV formats, and account settings
- `data/` directory structure: `transactions.csv` (all transactions), `accounts.json` (account balances), `goals.json` (savings goals)
