# CLAUDE.md

Guidance for Claude Code when working in this repository.

---

## Commands

```bash
# Run all tests (enforces 100% coverage)
pytest

# Run without coverage enforcement (faster)
pytest -p no:cov

# Lint and format
ruff check .          # lint (add --fix to auto-fix)
ruff format .         # format

# Pre-commit hooks
pre-commit install          # install hooks (one-time)
pre-commit run --all-files  # run all hooks on entire repo

# Run a single test file
pytest tests/test_data_store.py -v

# Run a single test
pytest tests/test_csv_parser.py::test_parse_chase_csv -v

# Import real bank statements
python3 -m importers.real_data

# CLI — common commands
python3 main.py summary --month 2026-01
python3 main.py top-categories --last 3months
python3 main.py dashboard             # generates + opens reports/dashboard.html
python3 main.py cards                 # show card portfolio, optimizer, and upgrade picks
python3 main.py dashboard --no-open   # generate only (used in tests)
python3 main.py networth
python3 main.py account update Robinhood --balance 7011.78 --type investment
```

---

## Architecture

### Data Flow

```
Bank PDFs/CSVs
    │
    ├── main.py import csv/pdf  →  importers/csv_parser.py or importers/pdf_parser.py
    └── importers/real_data.py  →  bank-specific regex parsers
                    │
                    ▼
            DataStore (data/transactions.csv)
                    │
                    ▼
            main.py CLI  →  summary, top-categories, spending, networth, goals
                    │
                    ▼
            dashboard/renderer.py + dashboard/analytics.py  →  reports/dashboard.html
```

**Flat-file storage:** `data/transactions.csv`, `data/accounts.json`, `data/goals.json`. No database.

### Key Modules

| Module | Responsibility |
|--------|---------------|
| `core/data_store.py` | `DataStore.add()`, `load()`, `update()`, `is_duplicate()`. `generate_id()` = 16-char SHA256 from `date+amount+merchant+account`. |
| `core/categorizer.py` | Longest-match-wins keyword lookup. `normalize_merchant()` lowercases, strips branch numbers and asterisks. Keywords in `config.json → categories`. |
| `core/goals.py` | Load/save `goals.json`. Named goals track `created` date for at-risk computation. |
| `core/cards.py` | `load_cards()`, `compute_optimal_card_per_category()`, `compute_card_annual_value()`, `compute_missed_rewards()`, `compute_upgrade_recommendations()`. `CURATED_CARDS` = 8 hardcoded upgrade candidates. |
| `importers/csv_parser.py` | Config-driven CSV parser. Amex uses `amount_sign: "inverted"` to flip signs. |
| `importers/pdf_parser.py` | Generic PDF parser via `pdfplumber.extract_table()`. Simple table-format PDFs only. |
| `importers/real_data.py` | Custom text-layout parsers for real Chase, BofA, Robinhood statements. Reads file paths from `statements_manifest.json` (gitignored). Account names from `config.json → import_accounts`. |
| `dashboard/renderer.py` | Thin orchestrator: `_load_files()` → `build_context()` → Jinja2 render. |
| `dashboard/analytics.py` | All analytics: `build_context()`, `compute_kpis()`, `compute_category_trends()`, `compute_health_score()`, `compute_actionable_cuts()`, `compute_action_plan()`, `compute_spending_pct_of_income()`, `compute_account_balances()`, `compute_top_merchants()`, `compute_card_intelligence()`. |
| `main.py` | Click CLI. All commands accept `--data-dir` (hidden, default `data/`) for test isolation. |
| `scripts/check_secrets.py` | Pre-commit hook: blocks commits with account numbers, card numbers, SSNs. |
| `scripts/check_changelog.py` | Pre-commit hook: warns when CHANGELOG.md has no [Unreleased] entry. |

### Sign Convention

- **Negative amount** = expense/debit
- **Positive amount** = income/credit
- Chase credit card PDFs: positive charge line → stored as `-abs(amount)`
- Amex CSVs: positive = expense, negated at parse time via `amount_sign: "inverted"` in config
- BofA checking: amounts keep their raw sign from the PDF

### Dashboard Template

`templates/dashboard.html.j2` — self-contained HTML with all assets inlined:
- **Chart.js** (`chart.min.js`) — no CDN dependency
- **DaisyUI** (`daisyui.min.css`) — CSS framework
- **Alpine.js** (`alpine.min.js`) — tab switching

5 tabs: Overview, Spending, Goals, Insights, Cards.

---

## Security

### What is gitignored

```
statements/              # Bank PDF/CSV statement files
statements_manifest.json # File paths to statements — copy from statements_manifest.example.json
data/transactions.csv
data/accounts.json
data/goals.json
data/cards.json
reports/
.worktrees/
```

### Pre-commit Hooks

Uses the [pre-commit](https://pre-commit.com) framework. Install once: `sh scripts/install_hooks.sh`

| Hook | What it does |
|------|-------------|
| `trailing-whitespace` | Strips trailing whitespace |
| `end-of-file-fixer` | Ensures files end with a newline |
| `check-yaml` / `check-json` | Validates YAML/JSON syntax |
| `check-merge-conflict` | Blocks unresolved merge conflict markers |
| `detect-private-key` | Blocks private key files |
| `no-commit-to-branch` | Prevents direct commits to `main` |
| `ruff` | Lints Python (auto-fixes with `--fix`) |
| `ruff-format` | Formats Python |
| `mypy` | Static type checking |
| `bandit` | Security-focused static analysis |
| `check-secrets` (local) | **Blocks** account numbers, card numbers, SSN patterns |
| `check-changelog` (local) | **Warns** when no `[Unreleased]` section in CHANGELOG.md |

Configuration: `pyproject.toml` (ruff, mypy, bandit), `.pre-commit-config.yaml` (hook versions/args).

Never commit real account numbers, card numbers, SSNs, or file paths pointing to real statement files.

---

## Tests

```bash
pytest              # all tests, 100% coverage enforced
pytest -p no:cov    # skip coverage check
```

- All test files live in `tests/`
- CLI tests use Click's `CliRunner` with `--data-dir` pointing to `tmp_path`
- PDF parser tests use fixtures in `tests/fixtures/` (pre-generated, committed)
- To regenerate fixtures: `python tests/fixtures/make_pdf_fixtures.py`
- `config.json` at the repo root is used by tests — changes to `categories` affect categorization test outcomes

---

## Documentation

All documentation lives in `docs/`:

| File | Contents |
|------|---------|
| `docs/ARCHITECTURE.md` | Full architecture, data models, extension points |
| `docs/SECURITY.md` | Security policy, sensitive data handling |
| `docs/CONTRIBUTING.md` | Development workflow, TDD, adding banks/categories |
| `docs/references/cli-reference.md` | CLI options for every command |
| `docs/references/transaction-schema.md` | Transaction CSV schema, deduplication |
| `docs/references/config-schema.md` | config.json schema |
| `docs/references/bank-formats.md` | Per-bank format details |
| `docs/references/dashboard-context.md` | Dashboard template context dict |
| `docs/references/health-score.md` | Health score algorithm |
| `docs/references/testing-guide.md` | Test patterns, fixtures, coverage |

---

## Changelog

Update `CHANGELOG.md` under `[Unreleased]` when making changes. Use [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
## [Unreleased]

### Added
- New feature description

### Fixed
- Bug fix description
```

When releasing: rename `[Unreleased]` to `[X.Y.Z] — YYYY-MM-DD` and add a new empty `[Unreleased]` section above it.
