# Finance Tracker — Cleanup, Documentation & Security Design Spec
**Date:** 2026-03-25
**Status:** Approved

---

## Overview

A single big-bang PR that hardens security, cleans up code quality, enforces 100% test coverage, and builds out comprehensive documentation across the finance-tracker project. No new user-facing features — this is purely a quality and safety pass.

---

## Goals

1. Eliminate sensitive identifiers (partial card numbers, real account names) from tracked code
2. Add a pre-commit hook that blocks secrets from being committed
3. Refactor `import_real_data.py` from global mutable state to clean pure functions
4. Add type hints to every public and private function across all modules
5. Remove dead code and redundant files
6. Enforce 100% test coverage via `pytest --cov-fail-under=100`
7. Write comprehensive documentation: docstrings, ARCHITECTURE.md, SECURITY.md, CONTRIBUTING.md, references/
8. Improve README.md and keep CLAUDE.md in sync
9. Create CHANGELOG.md in Keep-a-Changelog format with retroactive entries
10. Add a pre-commit reminder hook for CHANGELOG updates

---

## Section 1 — Security Hardening

### Problem
`import_real_data.py` is currently an untracked file that hardcodes:
- Real partial card numbers in account names (e.g., `Chase-CreditCard-XXXX`)
- Specific PDF filenames with encoded dates and account identifiers
- Absolute local path references

If this file were ever committed, those identifiers would leak permanently into git history.

### Solution

**1. Config-driven account names**

Add an `import_accounts` section to `config.json`:
```json
"import_accounts": {
  "chase_credit":    "Chase-CreditCard",
  "bofa_visa":       "BofA-Visa",
  "bofa_checking":   "BofA-Checking",
  "robinhood":       "Robinhood"
}
```

`import_real_data.py` reads account names from `config.json` at runtime. No card numbers or account identifiers appear in code. This refactor — combined with `statements_manifest.json` holding all filenames — is the primary security fix. `import_real_data.py` is therefore safe to commit and is NOT added to `.gitignore`.

**2. `statements_manifest.json` (gitignored)**

Statement filenames and parser metadata move to a gitignored manifest. The manifest schema differs per bank because each parser requires different metadata:

```json
{
  "chase_credit": [
    {
      "path": "statements/YYYYMMDD-statements-XXXX-.pdf",
      "closing_year": 2026,
      "closing_month": 1
    }
  ],
  "bofa_visa": [
    {
      "path": "statements/eStmt_YYYY-MM-DD.pdf",
      "year": 2026
    }
  ],
  "bofa_checking": [
    {
      "path": "statements/eStmt_YYYY-MM-DD.pdf"
    }
  ],
  "robinhood_csv": [
    {
      "path": "statements/transactions.CSV"
    }
  ],
  "robinhood_pdf": [
    {
      "path": "statements/<uuid>.pdf"
    }
  ]
}
```

**Schema key explanation per bank:**
- `chase_credit` — requires `closing_year` + `closing_month` because Chase transaction lines only show MM/DD; `infer_year()` uses the closing date to resolve the year
- `bofa_visa` — requires `year` only (single integer); BofA Visa lines include both MM/DD dates but not a year
- `bofa_checking` — no year metadata needed; BofA checking lines include MM/DD/YY which encodes the year directly
- `robinhood_csv` / `robinhood_pdf` — no metadata needed; dates are fully qualified in the files

A committed `statements_manifest.example.json` shows the structure with placeholder values exactly as shown above.

**3. Pre-commit secrets hook**

`scripts/check_secrets.py` — scans staged files for:
- Card-number-like patterns: `\d{4}-\d{4}` or sequences of 4+ digit groups
- Paths containing `statements/`
- Files under `data/` (`transactions.csv`, `accounts.json`, `goals.json`)
- Common secret patterns: account numbers, API keys, `.env` contents

Blocks the commit with a clear error message if any pattern matches.

**4. Pre-commit hook installation**

A `.git/hooks/pre-commit` shell script is created during setup to wire both scripts into git:

```bash
#!/bin/sh
python3 scripts/check_secrets.py "$@"
if [ $? -ne 0 ]; then
  exit 1
fi
python3 scripts/check_changelog.py "$@"
exit 0
```

`check_secrets.py` blocks (exit code 1 on failure); `check_changelog.py` warns only (always exit 0).

A `scripts/install_hooks.sh` helper script is committed that installs the hook:
```bash
#!/bin/sh
cp scripts/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
echo "Pre-commit hook installed."
```

`CONTRIBUTING.md` instructs developers to run `sh scripts/install_hooks.sh` after cloning.

**5. `.gitignore` additions**
```
statements_manifest.json
```

Note: `import_real_data.py` is NOT gitignored — once the config-driven refactor is complete, no sensitive data appears in the file.

---

## Section 2 — Code Cleanup

### 2.1 Fix `import_real_data.py` global state

**Current problem:** Module-level globals mutate as side effects:
```python
store = DataStore(...)       # global
cat = Categorizer(...)       # global
added_count = 0              # global counter
skipped_count = 0            # global counter
```

This makes functions impossible to test in isolation and causes subtle bugs if the module is imported multiple times.

**Solution:** Single clean entry point, parsers return counts:
```python
def run_import(
    config_path: str = "config.json",
    data_dir: str = "data",
    manifest_path: str = "statements_manifest.json"
) -> tuple[int, int]:
    """Run all statement imports. Returns (added, skipped)."""
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    cat = Categorizer(config_path=config_path)
    config = _load_config(config_path)
    manifest = _load_manifest(manifest_path)
    added, skipped = 0, 0
    # dispatch each parser, accumulate counts
    ...
    return added, skipped

if __name__ == "__main__":
    added, skipped = run_import()
    print(f"TOTAL: {added} new, {skipped} skipped")
```

Each parser (`parse_chase_pdf`, `parse_bofa_credit_pdf`, `parse_bofa_checking_pdf`, `parse_robinhood_csv`, `parse_robinhood_pdf`) becomes a pure function:
- Takes `store`, `cat`, filenames, and metadata as explicit arguments
- Returns `(added: int, skipped: int)`
- No global reads or writes

**Special case — `parse_bofa_checking_pdf`:** This parser derives its account name internally by reading the `Account number:` line from the PDF (last 4 digits → `BofA-XXXX`). In the refactored model it retains this internal detection behaviour — no `account` argument is passed. The manifest entry for `bofa_checking` has no account metadata because the account name comes from the file itself. This is intentional and should be documented in `docs/references/bank-formats.md`.

### 2.2 Type hints on all functions (public and private)

Every function and method across all modules — public and private (underscore-prefixed) — gets full type annotations and a docstring. Private helpers are treated the same as public ones for type hints because they are still testable and need to be clearly understood.

| Module | Key public signatures |
|--------|----------------------|
| `data_store.py` | `add(tx: dict) -> None`, `load() -> pd.DataFrame`, `is_duplicate(tx: dict) -> bool`, `update(tx_id: str, fields: dict) -> None` |
| `categorizer.py` | `categorize(merchant: str) -> str`, `normalize_merchant(merchant: str) -> str` |
| `goals.py` | `set_monthly_target(amount: float, data_dir: str) -> None`, `add_named_goal(...) -> None`, `get_goal_progress(data_dir: str) -> dict` |
| `dashboard_data.py` | `build_context(df: pd.DataFrame, accounts: dict, goals: dict, today: date \| None) -> dict` + all compute functions + all private helpers (`_score_to_grade`, `_get_at_risk_goals`, `_category_icon`) |
| `dashboard.py` | `build_dashboard(data_dir: str, output_path: str) -> str` |
| `importers/csv_parser.py` | `parse(filepath: str, bank: str, account: str) -> list[dict]` |
| `importers/pdf_parser.py` | `parse(filepath: str, bank: str, account: str) -> list[dict]` |
| `import_real_data.py` | `run_import(config_path: str, data_dir: str, manifest_path: str) -> tuple[int, int]`, all parsers, `_load_config`, `_load_manifest` |
| `finance.py` | `_run_store_import(store: DataStore, transactions: list[dict]) -> tuple[int, int]` |

### 2.3 Dead code and file removal

**`importers/pdf_parser.py` — KEEP**

The generic PDF parser is an active dependency: `finance.py import pdf` command imports and uses `PDFParser`. Removing it would break the CLI. It is kept, gets type hints and docstrings, and its tests remain. The `tests/fixtures/make_pdf_fixtures.py` fixture generator is also kept as it is needed to regenerate `chase_sample.pdf` if the fixture schema changes.

**Files to remove:**

None beyond what the refactor naturally eliminates (no standalone dead files identified once `pdf_parser.py` is kept).

**Inline imports to consolidate:** `finance.py` imports `pandas`, `datetime`, `json`, `os` inside command functions — move to top-level imports.

**Duplicate import loop:** `finance.py` has identical add/skip loop in both `import_csv` and `import_pdf` commands — extract to `_run_store_import(store, transactions)` private helper returning `(added: int, skipped: int)`.

### 2.4 100% Test Coverage

- `pytest-cov` added to `requirements.txt`
- `pytest.ini` configured:
  ```ini
  [pytest]
  addopts = --cov=. --cov-fail-under=100 --cov-report=term-missing
            --cov-omit=tests/fixtures/make_pdf_fixtures.py
  ```
  `make_pdf_fixtures.py` is a fixture generator script, not application code — it is omitted from coverage measurement. All other Python files under the project root are measured.
- **New fixtures required** for `import_real_data.py` parser coverage:
  - `tests/fixtures/bofa_visa_sample.pdf` — generated by extending `tests/fixtures/make_pdf_fixtures.py` with a BofA Visa format (MM/DD MM/DD DESCRIPTION REF# ACCT# AMOUNT)
  - `tests/fixtures/bofa_checking_sample.pdf` — generated similarly (MM/DD/YY DESCRIPTION AMOUNT)
  - `tests/fixtures/robinhood_sample.csv` — hand-authored CSV with date/description/amount rows
  - `tests/fixtures/robinhood_sample.pdf` — generated with Account Activity section containing sample transactions
  - All fixture generators use `reportlab` (already in `requirements.txt`)
  - All generated fixture PDFs are committed to `tests/fixtures/`

- New tests for:
  - `run_import()` end-to-end using a temp data dir and all new fixtures
  - Each parser individually: `parse_chase_pdf`, `parse_bofa_credit_pdf`, `parse_bofa_checking_pdf`, `parse_robinhood_csv`, `parse_robinhood_pdf`
  - `scripts/check_secrets.py` — unit tests for each detection pattern (match and no-match cases)
  - `scripts/check_changelog.py` — unit tests for staged-file detection logic
  - `_run_store_import()` helper in `finance.py`
  - All private helpers across modules that gain type hints

---

## Section 3 — Documentation

**Why docs live in `docs/` not the project root:** `README.md` and `CLAUDE.md` are root-level because they are the first files a developer or tool reads. All other documentation lives in `docs/` to keep the root clean. `README.md` links to everything in `docs/`.

### 3.1 Docstrings

Every public and private function and class across all modules gets a docstring:

```python
def function_name(param: type) -> return_type:
    """
    One-line summary of what this does.

    Args:
        param: Description of the parameter.

    Returns:
        Description of the return value.

    Raises:
        ValueError: When and why this is raised (if applicable).
    """
```

Modules get a top-level docstring explaining their single responsibility.

### 3.2 Documentation Structure

```
docs/
├── ARCHITECTURE.md              # System design, data flow, module map
├── SECURITY.md                  # Security model, sensitive data policy
├── CONTRIBUTING.md              # How to extend the project
├── references/
│   ├── transaction-schema.md    # Full transaction CSV field spec
│   ├── config-schema.md         # Every key in config.json
│   ├── cli-reference.md         # Every CLI command with examples
│   ├── dashboard-context.md     # build_context() return value spec
│   ├── bank-formats.md          # Per-bank parsing notes
│   ├── health-score.md          # Health score algorithm, all 5 dimensions
│   └── testing-guide.md         # Test structure, fixtures, coverage policy
└── superpowers/                 # Existing (unchanged)
    ├── specs/
    └── plans/
```

### 3.3 `docs/ARCHITECTURE.md` (300+ lines)

Sections:
- System overview with ASCII data-flow diagram
- Module responsibility table (owns / does not own)
- Data layer design (why flat files, append-only CSV, SHA256 dedup)
- Dashboard pipeline (load → build_context → Jinja2 → HTML)
- Sign convention (negative = expense, positive = income)
- Extension points (adding banks, categories, new dashboard tabs)
- Known limitations and future work (Plaid Phase 2)

### 3.4 `docs/SECURITY.md` (300+ lines)

Sections:
- Threat model (what we're protecting against)
- Sensitive data inventory (what files contain real data)
- Gitignore policy (what is blocked and why)
- Pre-commit hook design and installation (`scripts/install_hooks.sh`)
- Bypass procedure (how to skip hooks when genuinely needed)
- `statements_manifest.json` — purpose, schema, and example
- How to handle real statements safely
- Incident response (what to do if sensitive data is accidentally committed)

### 3.5 `docs/CONTRIBUTING.md` (300+ lines)

Sections:
- Development setup (clone, install, `sh scripts/install_hooks.sh`)
- Adding a new bank format (CSV and PDF)
- Adding new spending categories
- Writing and running tests (coverage requirement, adding fixtures)
- Commit conventions and changelog update process
- How to add a new dashboard tab
- How to add a new CLI command

### 3.6 `docs/references/` files

Each reference file is a deep-reference document (300+ lines for the technical ones):

| File | Contents |
|------|----------|
| `transaction-schema.md` | Every field, type, valid values, examples, edge cases |
| `config-schema.md` | Every key in config.json with type, default, description, including new `import_accounts` section |
| `cli-reference.md` | Every command, every flag, expected output, error cases |
| `dashboard-context.md` | Every key in `build_context()` return dict, types, examples |
| `bank-formats.md` | Chase/BofA/Amex/Robinhood: format quirks, sign conventions, manifest schema per bank |
| `health-score.md` | All 5 scoring dimensions, point allocations, grade scale, worked examples |
| `testing-guide.md` | Test file map, fixture descriptions, how to add fixtures, coverage policy, how to run |

### 3.7 `README.md` improvements

- Concise quick-start (3 steps, show expected terminal output)
- Troubleshooting section (top 5 common errors + fixes)
- Links to `docs/ARCHITECTURE.md`, `docs/CONTRIBUTING.md`, `docs/references/`
- Phase 2 section updated with actual Plaid integration plan

### 3.8 `CLAUDE.md` sync

- Add references to new docs files where relevant
- Keep existing content — it's the developer quick-reference, not the deep docs

---

## Section 4 — Changelog

### `CHANGELOG.md` format

```markdown
# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-03-25
### Added
- 4-tab HTML dashboard: Overview, Spending, Goals, Insights
- Health score algorithm (0–100, 5 dimensions) with letter grade
- Actionable cuts engine with per-category and subscription analysis
- Action plan generator linked to at-risk savings goals
- Spending % of income breakdown per category
- Top merchants table per month
- DaisyUI + Alpine.js + Chart.js fully inlined (no CDN dependency)

## [0.2.0] - 2026-03-24
### Added
- `dashboard_data.py` data layer with `build_context()` orchestrator
- `compute_kpis`, `compute_category_trends`, `compute_health_score`,
  `compute_actionable_cuts`, `compute_action_plan`,
  `compute_spending_pct_of_income`, `compute_account_balances`,
  `compute_top_merchants`
### Changed
- `dashboard.py` refactored to thin renderer delegating all logic to `dashboard_data.py`

## [0.1.0] - 2026-03-24
### Added
- CLI (`finance.py`) with commands: import csv/pdf, add, summary, top-categories,
  spending, networth, account update, tag, goal set/status, dashboard
- `DataStore` flat-file storage (append-only CSV, SHA256 dedup)
- `Categorizer` keyword-based auto-categorizer driven by `config.json`
- `CSVParser` with per-bank format profiles (Chase, BofA, Amex)
- `PDFParser` generic table-based PDF importer
- `import_real_data.py` custom parsers for Chase/BofA/Robinhood real statements
- Savings goals (`goals.py`) with monthly targets and named goals
- Integration test suite covering all CLI commands and dashboard generation
```

**Sections used:** `Added`, `Changed`, `Fixed`, `Removed`, `Security`, `Deprecated`

**Version scheme:** `MAJOR.MINOR.PATCH`
- New features → bump MINOR
- Bug fixes → bump PATCH
- Breaking changes → bump MAJOR

### Pre-commit reminder hook

`scripts/check_changelog.py` — checks if `CHANGELOG.md` has been modified when non-trivial files (`.py`, `.html`, `.json` config) are staged. If not, prints a warning:

```
⚠️  CHANGELOG.md not updated. Did you mean to add a changelog entry?
    (This is a reminder, not a blocker — commit will proceed.)
```

Warning only — always exits 0 (does not block the commit).

---

## Implementation Approach

Single big-bang PR containing all four areas. Suggested commit order within the PR:

1. Security (config-driven accounts, manifest, `.gitignore`, secrets hook, hook installation)
2. Code cleanup (refactor `import_real_data.py`, type hints + docstrings on all functions, dead code removal)
3. Tests (100% coverage — new fixtures, new test files, `pytest.ini` config)
4. Documentation (all docs files, README update, CLAUDE.md sync)
5. Changelog (`CHANGELOG.md` with retroactive history, reminder hook)

---

## Files Created / Modified Summary

| Action | File |
|--------|------|
| Modified | `config.json` — add `import_accounts` section |
| Modified | `import_real_data.py` — config-driven, pure functions, type hints, docstrings |
| Modified | `finance.py` — type hints, consolidate imports, extract `_run_store_import()` |
| Modified | `data_store.py` — type hints, docstrings |
| Modified | `categorizer.py` — type hints, docstrings |
| Modified | `goals.py` — type hints, docstrings |
| Modified | `dashboard.py` — type hints, docstrings |
| Modified | `dashboard_data.py` — type hints, docstrings |
| Modified | `importers/csv_parser.py` — type hints, docstrings |
| Modified | `importers/pdf_parser.py` — type hints, docstrings (kept, active CLI dependency) |
| Modified | `.gitignore` — add `statements_manifest.json` only |
| Modified | `README.md` — improved quick-start, troubleshooting, links |
| Modified | `CLAUDE.md` — sync with new docs |
| Modified | `tests/fixtures/make_pdf_fixtures.py` — extend to generate BofA + Robinhood fixtures |
| Modified | `requirements.txt` — add `pytest-cov` |
| Created | `statements_manifest.example.json` |
| Created | `scripts/check_secrets.py` |
| Created | `scripts/check_changelog.py` |
| Created | `scripts/pre-commit` — shell script calling both check scripts |
| Created | `scripts/install_hooks.sh` — copies pre-commit script into `.git/hooks/` |
| Created | `CHANGELOG.md` |
| Created | `docs/ARCHITECTURE.md` |
| Created | `docs/SECURITY.md` |
| Created | `docs/CONTRIBUTING.md` |
| Created | `docs/references/transaction-schema.md` |
| Created | `docs/references/config-schema.md` |
| Created | `docs/references/cli-reference.md` |
| Created | `docs/references/dashboard-context.md` |
| Created | `docs/references/bank-formats.md` |
| Created | `docs/references/health-score.md` |
| Created | `docs/references/testing-guide.md` |
| Created | `tests/fixtures/bofa_visa_sample.pdf` |
| Created | `tests/fixtures/bofa_checking_sample.pdf` |
| Created | `tests/fixtures/robinhood_sample.csv` |
| Created | `tests/fixtures/robinhood_sample.pdf` |
| Created | `tests/test_import_real_data.py` |
| Created | `tests/test_check_secrets.py` |
| Created | `tests/test_check_changelog.py` |
| Created | `pytest.ini` — `--cov-fail-under=100`, `--cov-report=term-missing` |
