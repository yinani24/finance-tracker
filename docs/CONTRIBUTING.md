# Contributing Guide

This guide explains how to extend, test, and maintain the finance-tracker project. Whether you're adding a new bank format, a new CLI command, or a new dashboard tab, this document gives you the full picture.

---

## Table of Contents

1. [Development Setup](#1-development-setup)
2. [Project Structure](#2-project-structure)
3. [Running Tests](#3-running-tests)
4. [Adding a New Bank CSV Format](#4-adding-a-new-bank-csv-format)
5. [Adding a New Bank PDF Parser](#5-adding-a-new-bank-pdf-parser)
6. [Adding New Spending Categories](#6-adding-new-spending-categories)
7. [Writing and Running Tests](#7-writing-and-running-tests)
8. [Commit Conventions](#8-commit-conventions)
9. [Changelog Update Process](#9-changelog-update-process)
10. [How to Add a New Dashboard Tab](#10-how-to-add-a-new-dashboard-tab)
11. [How to Add a New CLI Command](#11-how-to-add-a-new-cli-command)
12. [Code Style Guide](#12-code-style-guide)
13. [Security Guidelines](#13-security-guidelines)

---

## 1. Development Setup

### Prerequisites

- Python 3.10+
- pip
- Git

### Steps

```bash
# 1. Clone the repository
git clone <repo-url>
cd finance-tracker

# 2. Install dependencies
pip install -r requirements.txt

# 3. REQUIRED: Install the pre-commit security hooks
sh scripts/install_hooks.sh
# Output: "Pre-commit hook installed successfully."

# 4. Verify everything works
pytest tests/ -v
# Expected: all tests pass
```

### What install_hooks.sh Does

Copies `scripts/pre-commit` to `.git/hooks/pre-commit` and makes it executable. The pre-commit hook runs two checks before every commit:

1. **check_secrets.py** — blocks the commit if it detects card-number patterns, `statements/` path references, or sensitive `data/` files in staged files
2. **check_changelog.py** — prints a reminder if you haven't updated `CHANGELOG.md` alongside code changes (warning only, does not block)

See [docs/SECURITY.md](SECURITY.md) for full details.

---

## 2. Project Structure

```
finance-tracker/
├── finance.py                  # CLI entry point (Click commands)
├── data_store.py               # Flat-file transaction storage (CSV + SHA256 dedup)
├── categorizer.py              # Keyword-based auto-categorizer
├── goals.py                    # Savings goals read/write (goals.json)
├── dashboard.py                # Dashboard HTML generator (thin orchestrator)
├── dashboard_data.py           # All analytics computation (build_context)
├── import_real_data.py         # Real bank statement parsers (Chase, BofA, Robinhood)
├── importers/
│   ├── csv_parser.py           # Generic CSV importer (format profiles from config.json)
│   └── pdf_parser.py           # Generic PDF table importer
├── templates/
│   └── dashboard.html.j2       # Jinja2 dashboard template (DaisyUI + Alpine.js + Chart.js)
├── tests/
│   ├── fixtures/               # PDF and CSV test fixtures
│   │   ├── make_pdf_fixtures.py  # Fixture generator script (run to regenerate PDFs)
│   │   ├── chase_sample.pdf
│   │   ├── chase_sample.csv
│   │   ├── bofa_visa_sample.pdf
│   │   ├── bofa_checking_sample.pdf
│   │   ├── robinhood_sample.csv
│   │   └── robinhood_sample.pdf
│   ├── test_data_store.py
│   ├── test_categorizer.py
│   ├── test_goals.py
│   ├── test_csv_parser.py
│   ├── test_pdf_parser.py
│   ├── test_dashboard.py
│   ├── test_cli_import.py
│   ├── test_cli_summary.py
│   ├── test_import_real_data.py
│   ├── test_check_secrets.py
│   └── test_check_changelog.py
├── scripts/
│   ├── check_secrets.py        # Pre-commit: blocks sensitive data
│   ├── check_changelog.py      # Pre-commit: reminds to update CHANGELOG
│   ├── pre-commit              # Shell wrapper for both checks
│   └── install_hooks.sh        # Installs the pre-commit hook
├── config.json                 # Central configuration
├── pytest.ini                  # Coverage enforcement (100%)
├── requirements.txt
├── CHANGELOG.md
├── README.md
├── CLAUDE.md
└── docs/
    ├── ARCHITECTURE.md
    ├── SECURITY.md
    ├── CONTRIBUTING.md         # This file
    └── references/             # Deep-reference documentation
        ├── transaction-schema.md
        ├── config-schema.md
        ├── cli-reference.md
        ├── dashboard-context.md
        ├── bank-formats.md
        ├── health-score.md
        └── testing-guide.md
```

---

## 3. Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_data_store.py -v

# Run tests matching a name pattern
pytest tests/ -k "test_load" -v

# Run with coverage report (shows uncovered lines)
pytest tests/ --cov --cov-report=term-missing

# Run the full coverage-enforced suite (same as CI)
pytest tests/
```

**Coverage requirement: 100%.** This is enforced via `pytest.ini`. Any commit that reduces coverage below 100% will fail the test run. See [docs/references/testing-guide.md](references/testing-guide.md) for details on the test structure and how to add fixtures.

---

## 4. Adding a New Bank CSV Format

The CSV importer (`importers/csv_parser.py`) is driven by format profiles in `config.json → bank_formats`. Adding a new bank is three steps.

### Step 1: Identify the column names

Open the bank's CSV in a text editor or spreadsheet to find exact column headers:

```
Transaction Date,Description,Amount
01/15/2026,CHIPOTLE #1234,-45.20
01/16/2026,NETFLIX.COM,-15.99
```

### Step 2: Add the format profile to config.json

```json
"bank_formats": {
  "newbank": {
    "date_col": "Transaction Date",
    "amount_col": "Amount",
    "merchant_col": "Description",
    "amount_sign": "standard"
  }
}
```

- `amount_sign: "standard"` — negative = expense (most banks)
- `amount_sign: "inverted"` — positive = expense (Amex)

### Step 3: Test the import

```bash
python finance.py import csv ~/Downloads/newbank.csv --bank newbank --account NewBank-Checking
```

### Step 4: Add a fixture and test

1. Create `tests/fixtures/newbank_sample.csv` with 3–5 representative rows
2. Add a test case to `tests/test_csv_parser.py`:

```python
def test_parse_newbank_csv():
    parser = CSVParser()
    txs = parser.parse("tests/fixtures/newbank_sample.csv", bank="newbank", account="NewBank")
    assert len(txs) > 0
    assert all(tx["account"] == "NewBank" for tx in txs)
    assert all("id" in tx for tx in txs)
```

### Step 5: Update documentation

Add an entry to `docs/references/bank-formats.md` with the column quirks and sign convention for the new bank.

---

## 5. Adding a New Bank PDF Parser

Real bank PDF statements need custom regex parsers because their text layouts are bank-specific. These live in `import_real_data.py`.

### Step 1: Study the statement format

Open the PDF in a text editor after extracting text with `pdfplumber`:

```python
import pdfplumber
with pdfplumber.open("statements/your_statement.pdf") as pdf:
    for page in pdf.pages:
        print(page.extract_text())
```

Identify the line format for transactions. For example: `MM/DD MERCHANT REF# AMOUNT`

### Step 2: Add the parser function

Add to `import_real_data.py`, following the existing pattern:

```python
def parse_newbank_pdf(
    store: DataStore,
    cat: Categorizer,
    filepath: str,
    account: str,
) -> tuple[int, int]:
    """
    Parse a NewBank credit card PDF statement.

    Args:
        store: DataStore instance.
        cat: Categorizer instance.
        filepath: Path to the NewBank PDF.
        account: Account name to tag transactions with.

    Returns:
        (added, skipped) counts.
    """
    tx_re = re.compile(r'^(\d{2}/\d{2})\s+(.+?)\s+(-?[\d,]+\.\d{2})\s*$')
    added, skipped = 0, 0

    try:
        pdf_file = pdfplumber.open(filepath)
    except Exception:
        return 0, 0

    with pdf_file:
        for page in pdf_file.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                m = tx_re.match(line)
                if not m:
                    continue
                try:
                    date_part, merchant_raw, amount_str = m.group(1), m.group(2), m.group(3)
                    # ... parse and call _add_tx
                except Exception:
                    continue

    return added, skipped
```

### Step 3: Wire it into run_import()

Add a loop in `run_import()` following the pattern for other parsers:

```python
for entry in manifest.get("newbank", []):
    a, s = parse_newbank_pdf(
        store, cat, entry["path"],
        accounts.get("newbank", "NewBank"),
    )
    added += a; skipped += s
```

### Step 4: Update config.json and manifest example

Add to `config.json → import_accounts`:
```json
"newbank": "NewBank-Credit"
```

Add to `statements_manifest.example.json`:
```json
"newbank": [
  { "path": "statements/newbank_statement.pdf" }
]
```

### Step 5: Generate a fixture PDF

Add a `make_newbank_pdf(path)` function to `tests/fixtures/make_pdf_fixtures.py` that generates a synthetic PDF matching the bank's format, then add it to the `if __name__ == "__main__":` block.

Run: `python3 tests/fixtures/make_pdf_fixtures.py`

### Step 6: Write tests

Add to `tests/test_import_real_data.py`:

```python
def test_parse_newbank_pdf_returns_counts_for_fixture(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_newbank_pdf(
        tmp_store, cat, f"{FIXTURES}/newbank_sample.pdf", "NewBank"
    )
    assert added >= 0
    assert skipped >= 0

def test_parse_newbank_pdf_skips_when_file_missing(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_newbank_pdf(tmp_store, cat, "/nonexistent.pdf", "NewBank")
    assert added == 0
    assert skipped == 0
```

### Step 7: Update documentation

Add the bank's parsing quirks to `docs/references/bank-formats.md`.

---

## 6. Adding New Spending Categories

### Step 1: Add to config.json

```json
"categories": {
  "Healthcare": ["pharmacy", "cvs", "walgreens", "doctor", "hospital", "dental", "urgent care"],
  ...
}
```

Keywords are **lowercase substring matches**. The longest matching keyword wins (a keyword of `"whole foods market"` beats `"whole foods"`).

### Step 2: Test categorization

```bash
python finance.py summary
```

New transactions matching the keywords will be auto-categorized. Existing transactions keep their current category unless re-imported.

### Step 3: Re-categorize existing transactions (optional)

If you want existing transactions to pick up the new category, you can re-import or manually update via `finance.py tag`.

### Step 4: Update documentation

Update `docs/references/config-schema.md` with the new category and its keywords.

---

## 7. Writing and Running Tests

### Philosophy

- **TDD:** Write the failing test first, then implement
- **100% coverage:** Every line must be covered; `pytest.ini` enforces this
- **Behavior tests:** Tests verify what the code does, not how it does it

### Test Structure

Each module has a corresponding test file. See [docs/references/testing-guide.md](references/testing-guide.md) for the full map.

### Adding a Test

```python
# tests/test_my_module.py
import pytest
from my_module import my_function

def test_my_function_returns_expected_value():
    result = my_function("input")
    assert result == "expected"

def test_my_function_handles_edge_case():
    result = my_function("")
    assert result == "default"
```

### Adding a Fixture File

For CSV fixtures:
1. Create `tests/fixtures/mybank_sample.csv` with 3–5 rows
2. Reference it in tests: `parser.parse("tests/fixtures/mybank_sample.csv", ...)`

For PDF fixtures:
1. Add a generator function to `tests/fixtures/make_pdf_fixtures.py`
2. Run `python3 tests/fixtures/make_pdf_fixtures.py` to generate the file
3. Commit the generated PDF

### Checking Coverage

```bash
pytest tests/ --cov-report=term-missing
```

The `Missing` column shows which line numbers have no test coverage. Write tests that exercise those paths.

---

## 8. Commit Conventions

### Format

```
type: short description (imperative, lowercase)
```

### Types

| Type | When to use |
|------|------------|
| `feat:` | New user-facing feature (bumps MINOR version) |
| `fix:` | Bug fix (bumps PATCH version) |
| `refactor:` | Code improvement with no behavior change |
| `docs:` | Documentation only |
| `test:` | Test additions or fixes |
| `security:` | Security hardening |
| `chore:` | Dependency updates, tooling |

### Examples

```
feat: add spending trend chart to dashboard Overview tab
fix: handle missing amount column in BofA CSV format
refactor: extract _run_store_import helper in finance.py
docs: add bank-formats reference for Chase credit PDF
test: add 100% coverage for parse_robinhood_pdf
security: block statements/ path references in pre-commit hook
```

### Committing with Co-Authorship (when using Claude Code)

```bash
git commit -m "$(cat <<'EOF'
feat: add spending trend chart

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## 9. Changelog Update Process

The project uses [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

### When to Update

Update `CHANGELOG.md` for any commit that:
- Adds, changes, or removes user-facing behavior
- Changes a module's public API
- Adds or modifies security controls
- Makes a breaking change

The pre-commit hook will remind you if you forget.

### Which Section to Add To

| Section | When to use |
|---------|------------|
| `Added` | New features, new files, new commands |
| `Changed` | Behavior changes, refactors visible to users |
| `Fixed` | Bug fixes |
| `Removed` | Deleted features or files |
| `Security` | Security-related changes |
| `Deprecated` | Features that will be removed in a future version |

### Versioning

- New features → bump **MINOR** (0.3.0 → 0.4.0)
- Bug fixes → bump **PATCH** (0.4.0 → 0.4.1)
- Breaking changes → bump **MAJOR** (0.4.0 → 1.0.0)

### Example Entry

```markdown
## [0.4.1] - 2026-04-01
### Fixed
- `parse_bofa_credit_pdf` now correctly handles statements with no purchase section
### Added
- `--last` option for `finance.py top-categories` accepts `N` (integer) in addition to `Nmonths`
```

---

## 10. How to Add a New Dashboard Tab

The dashboard uses Alpine.js for tab switching and Chart.js for charts.

### Step 1: Add a compute function in dashboard_data.py

```python
def compute_my_data(df: pd.DataFrame, today: date | None = None) -> list[dict]:
    """
    Compute data for the new tab.

    Args:
        df: Full transaction DataFrame.
        today: Reference date; defaults to today.

    Returns:
        List of dicts with keys: name, value, ...
    """
    if today is None:
        today = date.today()
    # ... compute and return
    return []
```

### Step 2: Call it from build_context()

```python
def build_context(df, accounts, goals, today=None):
    ...
    my_data = compute_my_data(df, today=today)
    ...
    return {
        ...
        "my_data": my_data,
    }
```

### Step 3: Add the tab to the template

In `templates/dashboard.html.j2`, add a tab button:

```html
<button class="tab" :class="{'tab-active': activeTab === 'mydata'}"
        @click="activeTab = 'mydata'">
  My Data
</button>
```

And the tab panel:

```html
<div x-show="activeTab === 'mydata'">
  {% for item in my_data %}
    <div>{{ item.name }}: {{ item.value }}</div>
  {% endfor %}
</div>
```

### Step 4: Add tests

In `tests/test_dashboard.py`:

```python
def test_build_context_includes_my_data(sample_df, sample_accounts, sample_goals):
    ctx = build_context(sample_df, sample_accounts, sample_goals)
    assert "my_data" in ctx
    assert isinstance(ctx["my_data"], list)
```

### Step 5: Update documentation

Add the new key to `docs/references/dashboard-context.md`.

---

## 11. How to Add a New CLI Command

### Step 1: Add the command to finance.py

```python
@cli.command()
@click.option("--data-dir", default="data", hidden=True)
def my_command(data_dir: str) -> None:
    """Short description shown in --help."""
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    df = store.load()
    # ... compute and display
    console.print("result")
```

### Step 2: Add options with clear names

```python
@cli.command()
@click.option("--month", default=None, help="Month as YYYY-MM (default: current month)")
@click.option("--data-dir", default="data", hidden=True)
def my_command(month: Optional[str], data_dir: str) -> None:
    ...
```

### Step 3: Follow output conventions

- Use `rich.Table` for tabular data
- Use `console.print("[green]Success[/green]")` for success messages
- Use `console.print("[red]Error[/red]")` for errors
- Use `click.echo()` for simple single-line output

### Step 4: Write tests

```python
# tests/test_cli_my_command.py
from click.testing import CliRunner
from finance import cli

def test_my_command_runs_successfully(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["my-command", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
```

### Step 5: Update documentation

Add the command to `docs/references/cli-reference.md` with examples and flag descriptions.

---

## 12. Code Style Guide

### Type Hints

All functions — public and private — get full type hints:

```python
def compute_savings(income: float, expenses: float, target: float) -> dict[str, float]:
    ...

def _normalize_amount(raw: str) -> float:
    ...
```

Use `Optional[T]` (with `from typing import Optional`) for Python 3.9 compatibility, or `T | None` with `from __future__ import annotations`.

### Docstrings

All functions and classes get docstrings:

```python
def my_function(param: str) -> int:
    """
    One-line summary (imperative mood, no trailing period).

    Args:
        param: What this parameter represents.

    Returns:
        What is returned.

    Raises:
        ValueError: When and why this is raised.
    """
```

### No Global Mutable State

Module-level variables should be constants (`ALL_CAPS`) or configuration. No module-level mutable objects:

```python
# Bad
store = DataStore()  # module-level instance

# Good
def run():
    store = DataStore()  # function-scoped
```

### Pure Functions

Prefer functions that take inputs and return outputs with no side effects. Side effects (file I/O, printing) belong at entry points (`main()`, CLI commands).

---

## 13. Security Guidelines

See [docs/SECURITY.md](SECURITY.md) for the full security policy.

**Quick rules:**
- Never hardcode account numbers, card numbers, or partial card identifiers in source code
- Never commit files from `statements/`, `data/`, or `.env`
- Always run `sh scripts/install_hooks.sh` after cloning
- If you accidentally commit sensitive data: `git reset HEAD~1` immediately, before pushing
- Use `statements_manifest.json` (gitignored) for local file paths; update `statements_manifest.example.json` for the committed schema
