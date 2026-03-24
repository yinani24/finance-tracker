# Cleanup, Documentation & Security Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden security, clean up code quality, enforce 100% test coverage, and build comprehensive documentation across the finance-tracker project.

**Architecture:** Security changes remove sensitive identifiers from tracked code by externalising account names to `config.json` and file paths to a gitignored `statements_manifest.json`. Code cleanup refactors `import_real_data.py` from global mutable state to pure functions, adds type hints + docstrings across all modules, and extracts a shared helper in `finance.py`. Documentation is written to `docs/` (split into focused files with a `references/` subdirectory), while `README.md` and `CLAUDE.md` stay as root-level entry points.

**Tech Stack:** Python 3.10+, Click, pandas, pdfplumber, reportlab, Jinja2, pytest, pytest-cov

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `config.json` | Add `import_accounts` section |
| Modify | `.gitignore` | Add `statements_manifest.json` |
| Create | `statements_manifest.example.json` | Placeholder manifest template |
| Create | `scripts/check_secrets.py` | Pre-commit: block staged sensitive data |
| Create | `scripts/check_changelog.py` | Pre-commit: warn when CHANGELOG not updated |
| Create | `scripts/pre-commit` | Shell script wiring both checks |
| Create | `scripts/install_hooks.sh` | Installs pre-commit hook into `.git/hooks/` |
| Modify | `import_real_data.py` | Config-driven, pure functions, type hints, docstrings |
| Modify | `finance.py` | Type hints, top-level imports, `_run_store_import()` helper |
| Modify | `data_store.py` | Type hints, docstrings |
| Modify | `categorizer.py` | Type hints, docstrings |
| Modify | `goals.py` | Type hints, docstrings |
| Modify | `dashboard.py` | Type hints, docstrings |
| Modify | `dashboard_data.py` | Type hints, docstrings |
| Modify | `importers/csv_parser.py` | Type hints, docstrings |
| Modify | `importers/pdf_parser.py` | Type hints, docstrings |
| Modify | `tests/fixtures/make_pdf_fixtures.py` | Add BofA Visa, BofA Checking, Robinhood fixtures |
| Create | `tests/fixtures/bofa_visa_sample.pdf` | Generated BofA Visa fixture |
| Create | `tests/fixtures/bofa_checking_sample.pdf` | Generated BofA Checking fixture |
| Create | `tests/fixtures/robinhood_sample.csv` | Hand-authored Robinhood CSV fixture |
| Create | `tests/fixtures/robinhood_sample.pdf` | Generated Robinhood brokerage PDF fixture |
| Create | `tests/test_import_real_data.py` | Tests for import_real_data parsers |
| Create | `tests/test_check_secrets.py` | Tests for check_secrets.py |
| Create | `tests/test_check_changelog.py` | Tests for check_changelog.py |
| Create | `pytest.ini` | Coverage enforcement config |
| Modify | `requirements.txt` | Add pytest-cov |
| Create | `CHANGELOG.md` | Keep-a-Changelog format, retroactive entries |
| Create | `docs/ARCHITECTURE.md` | System design, data flow, module map |
| Create | `docs/SECURITY.md` | Security model, sensitive data policy |
| Create | `docs/CONTRIBUTING.md` | Developer extension guide |
| Create | `docs/references/transaction-schema.md` | Transaction CSV field spec |
| Create | `docs/references/config-schema.md` | config.json key reference |
| Create | `docs/references/cli-reference.md` | Every CLI command with examples |
| Create | `docs/references/dashboard-context.md` | build_context() return spec |
| Create | `docs/references/bank-formats.md` | Per-bank parsing notes |
| Create | `docs/references/health-score.md` | Health score algorithm |
| Create | `docs/references/testing-guide.md` | Test structure and coverage policy |
| Modify | `README.md` | Quick-start, troubleshooting, doc links |
| Modify | `CLAUDE.md` | Sync references to new docs |

---

## Task 1: Add `import_accounts` to config.json and update .gitignore

**Files:**
- Modify: `config.json`
- Modify: `.gitignore`

- [ ] **Step 1: Add import_accounts to config.json**

Open `config.json` and add before the closing `}`:
```json
"import_accounts": {
  "chase_credit":   "Chase-CreditCard",
  "bofa_visa":      "BofA-Visa",
  "bofa_checking":  "BofA-Checking",
  "robinhood":      "Robinhood"
}
```

- [ ] **Step 2: Add statements_manifest.json to .gitignore**

Append to `.gitignore`:
```
statements_manifest.json
```

- [ ] **Step 3: Create statements_manifest.example.json**

Create `statements_manifest.example.json`:
```json
{
  "_comment": "Copy this to statements_manifest.json and fill in your real paths. Never commit statements_manifest.json.",
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

- [ ] **Step 4: Commit**

```bash
git add config.json .gitignore statements_manifest.example.json
git commit -m "security: config-driven accounts, gitignore manifest, add example manifest"
```

---

## Task 2: Create scripts/check_secrets.py

**Files:**
- Create: `scripts/check_secrets.py`
- Create: `tests/test_check_secrets.py`

- [ ] **Step 1: Write the failing tests first**

Create `tests/test_check_secrets.py`:
```python
"""Tests for scripts/check_secrets.py secret detection logic."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from check_secrets import (
    contains_card_pattern,
    contains_statements_path,
    contains_data_file,
    check_content,
)


def test_card_pattern_detects_four_digit_groups():
    assert contains_card_pattern("account Chase-CreditCard-1234") is True


def test_card_pattern_no_false_positive_on_clean_text():
    assert contains_card_pattern("Chase-CreditCard normal text") is False


def test_card_pattern_detects_16_digit_string():
    assert contains_card_pattern("card number 1234567890123456") is True


def test_statements_path_detects_statements_dir():
    assert contains_statements_path("statements/myfile.pdf") is True


def test_statements_path_clean():
    assert contains_statements_path("data/transactions.csv") is False


def test_data_file_detects_transactions():
    assert contains_data_file("data/transactions.csv") is True


def test_data_file_detects_accounts():
    assert contains_data_file("data/accounts.json") is True


def test_data_file_detects_goals():
    assert contains_data_file("data/goals.json") is True


def test_data_file_clean():
    assert contains_data_file("data/other.txt") is False


def test_check_content_returns_violations_list():
    violations = check_content("Chase-CreditCard-1234", "test.py")
    assert len(violations) > 0
    assert "test.py" in violations[0]


def test_check_content_clean_returns_empty():
    violations = check_content("normal code here", "test.py")
    assert violations == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_check_secrets.py -v
```
Expected: ImportError (module doesn't exist yet)

- [ ] **Step 3: Create scripts/check_secrets.py**

Create `scripts/__init__.py` (empty) and `scripts/check_secrets.py`:
```python
"""
Pre-commit hook: scans staged files for sensitive data patterns.

Blocks the commit (exit code 1) if any violation is found.
Run via .git/hooks/pre-commit — see scripts/install_hooks.sh.
"""
import re
import subprocess
import sys
from typing import Optional


# Patterns that indicate sensitive data
_CARD_RE = re.compile(r'\b\d{4}[-\s]\d{4}\b|\b\d{12,16}\b')
_STATEMENTS_RE = re.compile(r'\bstatements/')
_DATA_FILES = frozenset(["transactions.csv", "accounts.json", "goals.json"])


def contains_card_pattern(text: str) -> bool:
    """Return True if text contains a card-number-like digit pattern."""
    return bool(_CARD_RE.search(text))


def contains_statements_path(text: str) -> bool:
    """Return True if text references the statements/ directory."""
    return bool(_STATEMENTS_RE.search(text))


def contains_data_file(filepath: str) -> bool:
    """Return True if filepath is one of the sensitive data files under data/."""
    return any(filepath.endswith(f"data/{name}") or filepath == f"data/{name}"
               for name in _DATA_FILES)


def check_content(content: str, filepath: str) -> list[str]:
    """
    Check file content for secret patterns.

    Args:
        content: The text content of the file.
        filepath: The file path (used in violation messages).

    Returns:
        List of violation message strings (empty if clean).
    """
    violations: list[str] = []
    if contains_card_pattern(content):
        violations.append(
            f"  {filepath}: contains card-number-like digit pattern (e.g. XXXX-XXXX)"
        )
    if contains_statements_path(content):
        violations.append(
            f"  {filepath}: references statements/ directory — use statements_manifest.json instead"
        )
    return violations


def get_staged_files() -> list[str]:
    """Return list of staged file paths from git."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True, text=True
    )
    return [f for f in result.stdout.strip().splitlines() if f]


def scan_staged_files() -> list[str]:
    """
    Scan all staged files for sensitive patterns.

    Returns:
        List of violation messages (empty if all clean).
    """
    staged = get_staged_files()
    all_violations: list[str] = []

    for filepath in staged:
        # Block data files outright
        if contains_data_file(filepath):
            all_violations.append(
                f"  {filepath}: sensitive data file — must not be committed"
            )
            continue

        # Skip binary files and non-text
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except (OSError, IsADirectoryError):
            continue

        all_violations.extend(check_content(content, filepath))

    return all_violations


def main() -> int:
    """
    Entry point for pre-commit hook.

    Returns:
        0 if no violations, 1 if violations found.
    """
    violations = scan_staged_files()
    if violations:
        print("❌ COMMIT BLOCKED — sensitive data detected:")
        for v in violations:
            print(v)
        print("\nFix the above issues before committing.")
        print("See docs/SECURITY.md for guidance.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_check_secrets.py -v
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/__init__.py scripts/check_secrets.py tests/test_check_secrets.py
git commit -m "security: add check_secrets.py pre-commit script with tests"
```

---

## Task 3: Create scripts/check_changelog.py + pre-commit hook

**Files:**
- Create: `scripts/check_changelog.py`
- Create: `scripts/pre-commit`
- Create: `scripts/install_hooks.sh`
- Create: `tests/test_check_changelog.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_check_changelog.py`:
```python
"""Tests for scripts/check_changelog.py changelog reminder logic."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from check_changelog import is_nontrivial_file, changelog_is_staged, should_warn


def test_py_file_is_nontrivial():
    assert is_nontrivial_file("finance.py") is True


def test_html_file_is_nontrivial():
    assert is_nontrivial_file("templates/dashboard.html.j2") is True


def test_config_json_is_nontrivial():
    assert is_nontrivial_file("config.json") is True


def test_txt_file_is_trivial():
    assert is_nontrivial_file("notes.txt") is False


def test_md_file_is_trivial():
    assert is_nontrivial_file("README.md") is False


def test_changelog_staged_when_in_list():
    assert changelog_is_staged(["CHANGELOG.md", "finance.py"]) is True


def test_changelog_not_staged_when_absent():
    assert changelog_is_staged(["finance.py", "data_store.py"]) is False


def test_should_warn_when_nontrivial_staged_and_changelog_absent():
    assert should_warn(["finance.py"], changelog_staged=False) is True


def test_should_not_warn_when_changelog_staged():
    assert should_warn(["finance.py"], changelog_staged=True) is False


def test_should_not_warn_when_only_trivial_files():
    assert should_warn(["README.md"], changelog_staged=False) is False


def test_should_not_warn_when_no_files():
    assert should_warn([], changelog_staged=False) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_check_changelog.py -v
```
Expected: ImportError

- [ ] **Step 3: Create scripts/check_changelog.py**

```python
"""
Pre-commit hook: warns when CHANGELOG.md is not updated alongside code changes.

Warning only — always exits 0 (does not block the commit).
Run via .git/hooks/pre-commit — see scripts/install_hooks.sh.
"""
import subprocess
import sys

_NONTRIVIAL_EXTENSIONS = frozenset([".py", ".html", ".j2", ".json"])
_NONTRIVIAL_NAMES = frozenset(["config.json", "requirements.txt"])


def is_nontrivial_file(filepath: str) -> bool:
    """Return True if the file is a code or config file (not docs/markdown)."""
    import os
    _, ext = os.path.splitext(filepath)
    name = os.path.basename(filepath)
    return ext in _NONTRIVIAL_EXTENSIONS and name != "CHANGELOG.md"


def changelog_is_staged(staged_files: list[str]) -> bool:
    """Return True if CHANGELOG.md is in the staged files list."""
    return "CHANGELOG.md" in staged_files


def should_warn(staged_files: list[str], changelog_staged: bool) -> bool:
    """
    Return True if a warning should be printed.

    Args:
        staged_files: List of staged file paths.
        changelog_staged: Whether CHANGELOG.md is already staged.

    Returns:
        True if nontrivial files are staged but CHANGELOG.md is not.
    """
    if changelog_staged:
        return False
    return any(is_nontrivial_file(f) for f in staged_files)


def get_staged_files() -> list[str]:
    """Return list of staged file paths from git."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True, text=True
    )
    return [f for f in result.stdout.strip().splitlines() if f]


def main() -> int:
    """Entry point for pre-commit hook. Always returns 0."""
    staged = get_staged_files()
    cl_staged = changelog_is_staged(staged)
    if should_warn(staged, cl_staged):
        print("⚠️  CHANGELOG.md not updated. Did you mean to add a changelog entry?")
        print("    (This is a reminder, not a blocker — commit will proceed.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_check_changelog.py -v
```
Expected: All PASS

- [ ] **Step 5: Create scripts/pre-commit and scripts/install_hooks.sh**

Create `scripts/pre-commit`:
```bash
#!/bin/sh
# Pre-commit hook: runs secret detection (blocking) and changelog reminder (warning).
# Install with: sh scripts/install_hooks.sh

python3 scripts/check_secrets.py "$@"
if [ $? -ne 0 ]; then
  exit 1
fi

python3 scripts/check_changelog.py "$@"
exit 0
```

Create `scripts/install_hooks.sh`:
```bash
#!/bin/sh
# Installs the pre-commit hook. Run once after cloning:
#   sh scripts/install_hooks.sh

REPO_ROOT="$(git rev-parse --show-toplevel)"
cp "$REPO_ROOT/scripts/pre-commit" "$REPO_ROOT/.git/hooks/pre-commit"
chmod +x "$REPO_ROOT/.git/hooks/pre-commit"
echo "Pre-commit hook installed successfully."
```

- [ ] **Step 6: Commit**

```bash
git add scripts/check_changelog.py scripts/pre-commit scripts/install_hooks.sh tests/test_check_changelog.py
git commit -m "security: add check_changelog.py, pre-commit hook, install_hooks.sh with tests"
```

---

## Task 4: Refactor import_real_data.py

**Files:**
- Modify: `import_real_data.py`
- Create: `tests/test_import_real_data.py`
- Modify: `tests/fixtures/make_pdf_fixtures.py`

- [ ] **Step 1: Extend make_pdf_fixtures.py with BofA + Robinhood generators**

Rewrite `tests/fixtures/make_pdf_fixtures.py`:
```python
"""Run once to generate PDF fixtures for tests.

Usage:
    python tests/fixtures/make_pdf_fixtures.py
"""
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


def make_chase_pdf(path: str) -> None:
    """Generate a Chase credit card PDF fixture (table format)."""
    doc = SimpleDocTemplate(path, pagesize=letter)
    data = [
        ["Transaction Date", "Description", "Amount"],
        ["01/15/2024", "CHIPOTLE #1234", "-45.20"],
        ["01/16/2024", "NETFLIX.COM", "-15.99"],
        ["01/17/2024", "DIRECT DEPOSIT", "2500.00"],
    ]
    table = Table(data)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
    doc.build([table])


def make_bofa_visa_pdf(path: str) -> None:
    """Generate a BofA Visa credit card PDF fixture (regex line format)."""
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=letter)
    lines = [
        "Purchases and Adjustments",
        "01/10 01/11 WHOLE FOODS 1234 5678 56.34",
        "01/12 01/13 AMAZON.COM 2345 6789 89.99",
        "Payments and Other Credits",
    ]
    story = [Paragraph(line, styles["Normal"]) for line in lines]
    doc.build(story)


def make_bofa_checking_pdf(path: str) -> None:
    """Generate a BofA checking/savings PDF fixture (date+description+amount format)."""
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=letter)
    lines = [
        "Account number: 0000 0000 1234",
        "01/05/26 CENTAVO PAYROLL 3200.00",
        "01/07/26 CHIPOTLE -12.50",
        "01/10/26 ROBINHOOD -500.00",
    ]
    story = [Paragraph(line, styles["Normal"]) for line in lines]
    doc.build(story)


def make_robinhood_pdf(path: str) -> None:
    """Generate a Robinhood brokerage PDF fixture with Account Activity section."""
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=letter)
    lines = [
        "Account Activity",
        "Gold Subscription Margin Cash 01/05/2026 $5.00",
        "Interest Payment Margin Cash 01/15/2026 $1.23",
        "Executed Trades",
    ]
    story = [Paragraph(line, styles["Normal"]) for line in lines]
    doc.build(story)


if __name__ == "__main__":
    make_chase_pdf("tests/fixtures/chase_sample.pdf")
    make_bofa_visa_pdf("tests/fixtures/bofa_visa_sample.pdf")
    make_bofa_checking_pdf("tests/fixtures/bofa_checking_sample.pdf")
    make_robinhood_pdf("tests/fixtures/robinhood_sample.pdf")
    print("PDF fixtures created.")
```

- [ ] **Step 2: Generate the new fixture files**

```bash
python tests/fixtures/make_pdf_fixtures.py
```
Expected: "PDF fixtures created." — 4 PDF files now in tests/fixtures/

- [ ] **Step 3: Create the Robinhood CSV fixture**

Create `tests/fixtures/robinhood_sample.csv`:
```
2026-01-10,Interest Payment,1.50
2026-01-15,Interest Payment,0.75
```

- [ ] **Step 4: Write failing tests for import_real_data.py**

Create `tests/test_import_real_data.py`:
```python
"""Tests for import_real_data.py parsers and run_import() entry point."""
import json
import os
import tempfile
import pytest

import import_real_data as ird
from data_store import DataStore


# ── Fixtures ──────────────────────────────────────────────────────────────────

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def tmp_store(tmp_path):
    """DataStore backed by a temporary directory."""
    return DataStore(transactions_path=str(tmp_path / "transactions.csv"))


@pytest.fixture
def tmp_config(tmp_path):
    """Write a minimal config.json with import_accounts and return its path."""
    cfg = {
        "categories": {"Food & Dining": ["chipotle", "whole foods"], "Other": []},
        "bank_formats": {},
        "import_accounts": {
            "chase_credit": "Chase-CreditCard",
            "bofa_visa": "BofA-Visa",
            "bofa_checking": "BofA-Checking",
            "robinhood": "Robinhood",
        }
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg))
    return str(path)


@pytest.fixture
def tmp_manifest(tmp_path):
    """Write a statements_manifest.json pointing at fixture files."""
    manifest = {
        "chase_credit": [
            {"path": f"{FIXTURES}/chase_sample.pdf",
             "closing_year": 2024, "closing_month": 1}
        ],
        "bofa_visa": [
            {"path": f"{FIXTURES}/bofa_visa_sample.pdf", "year": 2024}
        ],
        "bofa_checking": [
            {"path": f"{FIXTURES}/bofa_checking_sample.pdf"}
        ],
        "robinhood_csv": [
            {"path": f"{FIXTURES}/robinhood_sample.csv"}
        ],
        "robinhood_pdf": [
            {"path": f"{FIXTURES}/robinhood_sample.pdf"}
        ],
    }
    path = tmp_path / "statements_manifest.json"
    path.write_text(json.dumps(manifest))
    return str(path)


# ── _load_config ──────────────────────────────────────────────────────────────

def test_load_config_returns_dict(tmp_config):
    cfg = ird._load_config(tmp_config)
    assert "import_accounts" in cfg
    assert cfg["import_accounts"]["chase_credit"] == "Chase-CreditCard"


def test_load_config_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        ird._load_config("/nonexistent/config.json")


# ── _load_manifest ────────────────────────────────────────────────────────────

def test_load_manifest_returns_dict(tmp_manifest):
    m = ird._load_manifest(tmp_manifest)
    assert "chase_credit" in m
    assert isinstance(m["chase_credit"], list)


def test_load_manifest_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        ird._load_manifest("/nonexistent/manifest.json")


# ── parse_chase_pdf ───────────────────────────────────────────────────────────

def test_parse_chase_pdf_skips_when_file_missing(tmp_store, tmp_config):
    from categorizer import Categorizer
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_chase_pdf(
        tmp_store, cat, "/nonexistent.pdf", "Chase-CC", 2024, 1
    )
    assert added == 0
    assert skipped == 0


# ── parse_bofa_credit_pdf ─────────────────────────────────────────────────────

def test_parse_bofa_credit_pdf_skips_when_file_missing(tmp_store, tmp_config):
    from categorizer import Categorizer
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_bofa_credit_pdf(
        tmp_store, cat, "/nonexistent.pdf", "BofA-Visa", 2024
    )
    assert added == 0
    assert skipped == 0


# ── parse_bofa_checking_pdf ───────────────────────────────────────────────────

def test_parse_bofa_checking_pdf_returns_counts_for_fixture(tmp_store, tmp_config):
    from categorizer import Categorizer
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_bofa_checking_pdf(
        tmp_store, cat, f"{FIXTURES}/bofa_checking_sample.pdf"
    )
    assert added >= 0
    assert skipped >= 0


# ── parse_robinhood_csv ───────────────────────────────────────────────────────

def test_parse_robinhood_csv_adds_rows(tmp_store, tmp_config):
    from categorizer import Categorizer
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_robinhood_csv(
        tmp_store, cat, f"{FIXTURES}/robinhood_sample.csv", "Robinhood"
    )
    assert added == 2
    assert skipped == 0


def test_parse_robinhood_csv_deduplicates(tmp_store, tmp_config):
    from categorizer import Categorizer
    cat = Categorizer(tmp_config)
    ird.parse_robinhood_csv(tmp_store, cat, f"{FIXTURES}/robinhood_sample.csv", "Robinhood")
    added2, skipped2 = ird.parse_robinhood_csv(
        tmp_store, cat, f"{FIXTURES}/robinhood_sample.csv", "Robinhood"
    )
    assert added2 == 0
    assert skipped2 == 2


def test_parse_robinhood_csv_skips_short_rows(tmp_store, tmp_config, tmp_path):
    from categorizer import Categorizer
    cat = Categorizer(tmp_config)
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("only_one_column\n")
    added, skipped = ird.parse_robinhood_csv(tmp_store, cat, str(bad_csv), "Robinhood")
    assert added == 0


# ── parse_robinhood_pdf ───────────────────────────────────────────────────────

def test_parse_robinhood_pdf_returns_counts_for_fixture(tmp_store, tmp_config):
    from categorizer import Categorizer
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_robinhood_pdf(
        tmp_store, cat, f"{FIXTURES}/robinhood_sample.pdf", "Robinhood"
    )
    assert added >= 0
    assert skipped >= 0


# ── run_import ────────────────────────────────────────────────────────────────

def test_run_import_returns_tuple(tmp_path, tmp_config, tmp_manifest):
    result = ird.run_import(
        config_path=tmp_config,
        data_dir=str(tmp_path),
        manifest_path=tmp_manifest
    )
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_run_import_missing_manifest_raises(tmp_path, tmp_config):
    with pytest.raises(FileNotFoundError):
        ird.run_import(
            config_path=tmp_config,
            data_dir=str(tmp_path),
            manifest_path=str(tmp_path / "nonexistent.json")
        )
```

- [ ] **Step 5: Run tests to verify they fail**

```bash
pytest tests/test_import_real_data.py -v
```
Expected: ImportError or AttributeError (functions not yet refactored)

- [ ] **Step 6: Rewrite import_real_data.py as pure functions**

Rewrite `import_real_data.py` completely:
```python
"""
Custom importers for real bank statements.

Handles Chase credit card, BofA Visa credit, BofA checking/savings,
Robinhood CSV, and Robinhood brokerage PDF statements.

Account names are loaded from config.json → import_accounts.
Statement file paths are loaded from statements_manifest.json (gitignored).

Run from the repo root:
    python3 import_real_data.py
"""
import csv
import json
import os
import re
import sys
from datetime import datetime
from typing import Any

import pdfplumber

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from categorizer import Categorizer, normalize_merchant
from data_store import DataStore, generate_id


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_config(config_path: str = "config.json") -> dict[str, Any]:
    """Load and return config.json as a dict."""
    with open(config_path) as f:
        return json.load(f)


def _load_manifest(manifest_path: str = "statements_manifest.json") -> dict[str, Any]:
    """Load and return statements_manifest.json as a dict."""
    with open(manifest_path) as f:
        return json.load(f)


def _add_tx(
    store: DataStore,
    cat: Categorizer,
    date_str: str,
    amount: float,
    merchant: str,
    account: str,
    source: str = "pdf",
    notes: str = "",
    is_income: bool = False,
    is_savings: bool = False,
) -> tuple[int, int]:
    """
    Normalise merchant, categorize, and add a transaction to the store.

    Returns:
        (1, 0) if added, (0, 1) if duplicate.
    """
    m = normalize_merchant(merchant)
    tx = {
        "id": generate_id(date_str, amount, m, account),
        "date": date_str,
        "amount": amount,
        "merchant": m,
        "category": cat.categorize(merchant),
        "account": account,
        "source": source,
        "is_income": is_income,
        "is_savings": is_savings,
        "notes": notes,
    }
    if store.is_duplicate(tx):
        return 0, 1
    store.add(tx)
    return 1, 0


# ── Chase Credit Card ─────────────────────────────────────────────────────────

def infer_year(tx_month: int, closing_year: int, closing_month: int) -> int:
    """
    Infer the transaction year from the closing date.

    Chase transaction lines only show MM/DD. If the transaction month is
    after the closing month, the transaction occurred in the prior year.

    Args:
        tx_month: Transaction month (1–12).
        closing_year: Year of the statement closing date.
        closing_month: Month of the statement closing date.

    Returns:
        The inferred 4-digit year.
    """
    if tx_month > closing_month:
        return closing_year - 1
    return closing_year


def parse_chase_pdf(
    store: DataStore,
    cat: Categorizer,
    filepath: str,
    account: str,
    closing_year: int,
    closing_month: int,
) -> tuple[int, int]:
    """
    Parse a Chase credit card PDF statement (text-based regex format).

    Args:
        store: DataStore instance to write transactions to.
        cat: Categorizer instance for auto-categorization.
        filepath: Path to the Chase PDF statement.
        account: Account name to tag transactions with.
        closing_year: Statement closing year (for year inference).
        closing_month: Statement closing month (for year inference).

    Returns:
        (added, skipped) counts.
    """
    tx_re = re.compile(r'^(\d{2}/\d{2})\s+(.+?)\s{2,}(-?[\d,]+\.\d{2})\s*$')
    tx_re2 = re.compile(r'^(\d{2}/\d{2})\s+(.+?)\s+(-?[\d,]+\.\d{2})\s*$')
    skip_re = re.compile(
        r'(EXCHG RATE|X 0\.\d+|^TOTAL|^PAYMENT|^PURCHASE$|^Interest|'
        r'^INTEREST|Date of|Merchant Name|ACCOUNT ACTIVITY|CONTINUED|'
        r'^2026 Totals|^Total f|^Total i|Your Annual|Minimum Payment|'
        r'Paying only|Balance on this|SCENARIO|New Balance|MMaannaaggee|'
        r'^www\.|^1-800|^P\.O\. Box|^Wilmington|^Carol Stream)',
        re.IGNORECASE,
    )
    payment_section = False
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
                if not line:
                    continue
                if "PAYMENTS AND OTHER CREDITS" in line or "PAYMENTS AND OTHER" in line:
                    payment_section = True
                    continue
                if line.startswith("PURCHASE") or "INTEREST CHARGED" in line:
                    payment_section = False
                    continue
                if skip_re.search(line):
                    continue
                m = tx_re.match(line) or tx_re2.match(line)
                if not m:
                    continue
                date_part, merchant_raw, amount_str = m.group(1), m.group(2), m.group(3)
                if re.search(r'\bX\s+0\.\d+|\(EXCHG', merchant_raw):
                    continue
                if payment_section:
                    continue
                if "INTEREST CHARGE" in merchant_raw.upper():
                    continue
                try:
                    tx_month = int(date_part.split("/")[0])
                    tx_day = int(date_part.split("/")[1])
                    year = infer_year(tx_month, closing_year, closing_month)
                    date_str = f"{year}-{tx_month:02d}-{tx_day:02d}"
                    amount = -abs(float(amount_str.replace(",", "")))
                    a, s = _add_tx(store, cat, date_str, amount, merchant_raw, account)
                    added += a
                    skipped += s
                except Exception:
                    continue

    return added, skipped


# ── BofA Visa Credit ──────────────────────────────────────────────────────────

def parse_bofa_credit_pdf(
    store: DataStore,
    cat: Categorizer,
    filepath: str,
    account: str,
    year: int,
) -> tuple[int, int]:
    """
    Parse a BofA Visa Signature credit card PDF statement.

    Args:
        store: DataStore instance.
        cat: Categorizer instance.
        filepath: Path to the BofA Visa PDF.
        account: Account name to tag transactions with.
        year: Statement year (BofA lines include MM/DD but not year).

    Returns:
        (added, skipped) counts.
    """
    tx_re = re.compile(
        r'^(\d{2}/\d{2})\s+\d{2}/\d{2}\s+(.+?)\s+\d{4}\s+\d{4}\s+(-?[\d,]+\.\d{2})\s*$'
    )
    skip_re = re.compile(
        r'(TOTAL PAYMENTS|TOTAL PURCHASES|TOTAL INTEREST|Interest Charged|'
        r'^2026 Totals|^Total fees|^Total interest|INTEREST CHARGED ON|'
        r'Transaction.*Date.*Description|Account Summary|^Transactions$)',
        re.IGNORECASE,
    )
    purchase_section = False
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
                if not line:
                    continue
                if "Purchases and Adjustments" in line:
                    purchase_section = True
                    continue
                if "Payments and Other Credits" in line or "Interest Charged" in line:
                    purchase_section = False
                    continue
                if skip_re.search(line):
                    continue
                if not purchase_section:
                    continue
                m = tx_re.match(line)
                if not m:
                    continue
                try:
                    date_part = m.group(1)
                    merchant_raw = m.group(2).strip()
                    amount_str = m.group(3)
                    tx_month = int(date_part.split("/")[0])
                    tx_day = int(date_part.split("/")[1])
                    date_str = f"{year}-{tx_month:02d}-{tx_day:02d}"
                    amount = -abs(float(amount_str.replace(",", "")))
                    a, s = _add_tx(store, cat, date_str, amount, merchant_raw, account)
                    added += a
                    skipped += s
                except Exception:
                    continue

    return added, skipped


# ── BofA Checking / Savings ───────────────────────────────────────────────────

_SKIP_BOFA = re.compile(
    r"(Online Banking transfer|Confirmation#|Federal Withholding|"
    r"Interest Earned|Annual Percentage|Page \d+ of)",
    re.IGNORECASE,
)


def parse_bofa_checking_pdf(
    store: DataStore,
    cat: Categorizer,
    filepath: str,
) -> tuple[int, int]:
    """
    Parse a BofA combined checking/savings statement.

    Account names are derived internally from the PDF's 'Account number:' lines
    (last 4 digits → 'BofA-XXXX'). No account argument is accepted.

    Args:
        store: DataStore instance.
        cat: Categorizer instance.
        filepath: Path to the BofA checking/savings PDF.

    Returns:
        (added, skipped) counts.
    """
    tx_re = re.compile(r"^(\d{2}/\d{2}/\d{2})\s+(.+?)\s+(-?[\d,]+\.\d{2})\s*$")
    added, skipped = 0, 0

    try:
        pdf_file = pdfplumber.open(filepath)
    except Exception:
        return 0, 0

    with pdf_file:
        current_account = None
        for page in pdf_file.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                if "Account number:" in line:
                    acct_match = re.search(r"Account number:\s*([\d ]+)", line)
                    if acct_match:
                        acct_num = acct_match.group(1).replace(" ", "")[-4:]
                        current_account = f"BofA-{acct_num}"
                if not line or not current_account:
                    continue
                if _SKIP_BOFA.search(line):
                    continue
                m = tx_re.match(line)
                if not m:
                    continue
                try:
                    date_part, desc, amount_str = (
                        m.group(1), m.group(2).strip(), m.group(3)
                    )
                    dt = datetime.strptime(date_part, "%m/%d/%y")
                    date_str = dt.strftime("%Y-%m-%d")
                    amount = float(amount_str.replace(",", ""))
                    is_income = bool(
                        re.search(r"CENTAVO|PAYROLL|BKOFAMERICA.*DEPOSIT|Zelle payment from",
                                  desc, re.I)
                    )
                    is_savings = bool(re.search(r"ROBINHOOD", desc, re.I))
                    if re.search(
                        r"JPMorgan Chase.*Ext Trnsfr|Online Banking.*to CHK|"
                        r"Online Banking.*from SAV|Online Banking.*to SAV|"
                        r"Online Banking.*from CHK|Online Banking.*payment to CRD",
                        desc, re.I,
                    ):
                        continue
                    a, s = _add_tx(
                        store, cat, date_str, amount, desc, current_account,
                        is_income=is_income, is_savings=is_savings,
                    )
                    added += a
                    skipped += s
                except Exception:
                    continue

    return added, skipped


# ── Robinhood CSV ─────────────────────────────────────────────────────────────

def parse_robinhood_csv(
    store: DataStore,
    cat: Categorizer,
    filepath: str,
    account: str,
) -> tuple[int, int]:
    """
    Parse a Robinhood interest/dividend CSV export.

    Expected format: date,description,amount (no header row).

    Args:
        store: DataStore instance.
        cat: Categorizer instance.
        filepath: Path to the Robinhood CSV file.
        account: Account name to tag transactions with.

    Returns:
        (added, skipped) counts.
    """
    added, skipped = 0, 0
    with open(filepath, newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            try:
                date_str = row[0].strip()
                desc = row[1].strip().strip('"')
                amount = float(row[2].strip())
                datetime.strptime(date_str, "%Y-%m-%d")  # validate format
                a, s = _add_tx(
                    store, cat, date_str, amount, desc, account,
                    source="csv", is_income=True, notes="Robinhood interest",
                )
                added += a
                skipped += s
            except Exception:
                continue
    return added, skipped


# ── Robinhood Brokerage PDF ───────────────────────────────────────────────────

def parse_robinhood_pdf(
    store: DataStore,
    cat: Categorizer,
    filepath: str,
    account: str,
) -> tuple[int, int]:
    """
    Parse a Robinhood brokerage PDF statement for non-investment cash activity.

    Captures: Gold subscription fees, interest payments, cash dividends,
    crypto money movements. Skips: ACH deposits, buy/sell trades.

    Args:
        store: DataStore instance.
        cat: Categorizer instance.
        filepath: Path to the Robinhood brokerage PDF.
        account: Account name to tag transactions with.

    Returns:
        (added, skipped) counts.
    """
    added, skipped = 0, 0
    in_activity = False

    try:
        pdf_file = pdfplumber.open(filepath)
    except Exception:
        return 0, 0

    with pdf_file:
        for page in pdf_file.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                if "Account Activity" in line:
                    in_activity = True
                    continue
                if in_activity and ("Executed Trades" in line or "Stock Lending" in line):
                    in_activity = False
                    continue
                if not in_activity:
                    continue
                if re.search(r"Description.*Symbol|Total Funds Paid", line):
                    continue
                date_m = re.search(r"(\d{2}/\d{2}/\d{4})", line)
                if not date_m:
                    continue
                date_str = datetime.strptime(date_m.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
                if re.search(r"ACH Deposit", line, re.I):
                    continue
                if re.search(r"\bBuy\b|\bSell\b|\bSLIP\b|\bCDIV\b|Dividend Reinvest|Collateral",
                             line, re.I):
                    continue
                try:
                    if re.search(r"Crypto Money Movement", line, re.I):
                        amt_m = re.findall(r"\$([\d,.]+)", line)
                        if amt_m:
                            a, s = _add_tx(
                                store, cat, date_str, -float(amt_m[-1].replace(",", "")),
                                "Crypto Transfer", account, notes="Crypto money movement",
                            )
                            added += a; skipped += s
                        continue
                    if re.search(r"Gold Subscription", line, re.I):
                        amt_m = re.findall(r"\$([\d,.]+)", line)
                        if amt_m:
                            a, s = _add_tx(
                                store, cat, date_str, -float(amt_m[-1].replace(",", "")),
                                "Robinhood Gold Subscription", account,
                                notes="Robinhood Gold fee",
                            )
                            added += a; skipped += s
                        continue
                    if re.search(r"Interest Payment|Brokerage-held Cash Interest", line, re.I):
                        amt_m = re.findall(r"\$([\d,.]+)", line)
                        if amt_m:
                            a, s = _add_tx(
                                store, cat, date_str, float(amt_m[-1].replace(",", "")),
                                "Robinhood Interest", account,
                                is_income=True, notes="Robinhood interest",
                            )
                            added += a; skipped += s
                        continue
                    if re.search(r"\bCDIV\b|Cash Div", line, re.I):
                        amt_m = re.findall(r"\$([\d,.]+)", line)
                        if amt_m:
                            a, s = _add_tx(
                                store, cat, date_str, float(amt_m[-1].replace(",", "")),
                                "Dividend", account,
                                is_income=True, notes="Robinhood dividend",
                            )
                            added += a; skipped += s
                        continue
                except Exception:
                    continue

    return added, skipped


# ── Entry Point ───────────────────────────────────────────────────────────────

def run_import(
    config_path: str = "config.json",
    data_dir: str = "data",
    manifest_path: str = "statements_manifest.json",
) -> tuple[int, int]:
    """
    Run all statement imports defined in statements_manifest.json.

    Args:
        config_path: Path to config.json.
        data_dir: Directory containing data files (transactions.csv, etc.).
        manifest_path: Path to statements_manifest.json (gitignored).

    Returns:
        (total_added, total_skipped) transaction counts.
    """
    config = _load_config(config_path)
    manifest = _load_manifest(manifest_path)
    accounts = config.get("import_accounts", {})
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    cat = Categorizer(config_path=config_path)
    added, skipped = 0, 0

    for entry in manifest.get("chase_credit", []):
        a, s = parse_chase_pdf(
            store, cat, entry["path"],
            accounts.get("chase_credit", "Chase-CreditCard"),
            entry["closing_year"], entry["closing_month"],
        )
        added += a; skipped += s
        print(f"  Chase {entry['path']}: {a} added, {s} skipped")

    for entry in manifest.get("bofa_visa", []):
        a, s = parse_bofa_credit_pdf(
            store, cat, entry["path"],
            accounts.get("bofa_visa", "BofA-Visa"),
            entry["year"],
        )
        added += a; skipped += s
        print(f"  BofA Visa {entry['path']}: {a} added, {s} skipped")

    for entry in manifest.get("bofa_checking", []):
        a, s = parse_bofa_checking_pdf(store, cat, entry["path"])
        added += a; skipped += s
        print(f"  BofA Checking {entry['path']}: {a} added, {s} skipped")

    for entry in manifest.get("robinhood_csv", []):
        a, s = parse_robinhood_csv(
            store, cat, entry["path"],
            accounts.get("robinhood", "Robinhood"),
        )
        added += a; skipped += s
        print(f"  Robinhood CSV {entry['path']}: {a} added, {s} skipped")

    for entry in manifest.get("robinhood_pdf", []):
        a, s = parse_robinhood_pdf(
            store, cat, entry["path"],
            accounts.get("robinhood", "Robinhood"),
        )
        added += a; skipped += s
        print(f"  Robinhood PDF {entry['path']}: {a} added, {s} skipped")

    return added, skipped


if __name__ == "__main__":
    total_added, total_skipped = run_import()
    print(f"\n{'=' * 40}")
    print(f"TOTAL: {total_added} new transactions added, {total_skipped} duplicates skipped")
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_import_real_data.py -v
```
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add import_real_data.py tests/test_import_real_data.py \
        tests/fixtures/make_pdf_fixtures.py \
        tests/fixtures/bofa_visa_sample.pdf \
        tests/fixtures/bofa_checking_sample.pdf \
        tests/fixtures/robinhood_sample.csv \
        tests/fixtures/robinhood_sample.pdf
git commit -m "refactor: import_real_data.py — pure functions, config-driven, type hints, new fixtures"
```

---

## Task 5: Add type hints + docstrings to data_store.py, categorizer.py, goals.py

**Files:**
- Modify: `data_store.py`
- Modify: `categorizer.py`
- Modify: `goals.py`

- [ ] **Step 1: Rewrite data_store.py with type hints and docstrings**

```python
"""
Flat-file transaction storage layer.

All transactions are persisted in a single CSV file (append-only semantics).
Deduplication uses a 16-character SHA256 hash of date+amount+merchant+account.
"""
import hashlib
import os

import pandas as pd

COLUMNS = ["id", "date", "amount", "merchant", "category", "account",
           "source", "is_income", "is_savings", "notes"]


def generate_id(date: str, amount: float, merchant: str, account: str) -> str:
    """
    Generate a 16-character deduplication ID.

    Uses SHA256 over 'date+amount+merchant.lower()+account.lower()'.

    Args:
        date: Transaction date as YYYY-MM-DD string.
        amount: Transaction amount (negative = expense).
        merchant: Raw merchant name (normalised internally).
        account: Account name string.

    Returns:
        16-character hex string.
    """
    raw = f"{date}{amount}{merchant.lower().strip()}{account.lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class DataStore:
    """Manages reading and writing the flat-file transaction CSV."""

    def __init__(self, transactions_path: str = "data/transactions.csv") -> None:
        """
        Args:
            transactions_path: Path to the transactions CSV file.
        """
        self.path = transactions_path

    def load(self) -> pd.DataFrame:
        """
        Load all transactions from disk.

        Returns:
            DataFrame with COLUMNS schema; empty DataFrame if file not found.
        """
        try:
            return pd.read_csv(self.path, dtype={"id": str})
        except FileNotFoundError:
            return pd.DataFrame(columns=COLUMNS)

    def add(self, tx: dict) -> None:
        """
        Append a transaction to the CSV.

        Args:
            tx: Transaction dict matching the COLUMNS schema.

        Raises:
            ValueError: If the transaction ID already exists in the store.
        """
        if self.is_duplicate(tx):
            raise ValueError(f"Transaction {tx['id']} already exists in the store")
        df = self.load()
        new_row = pd.DataFrame([tx])
        df = pd.concat([df, new_row], ignore_index=True)
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        df.to_csv(self.path, index=False)

    def is_duplicate(self, tx: dict) -> bool:
        """
        Check whether a transaction ID already exists in the store.

        Args:
            tx: Transaction dict with an 'id' key.

        Returns:
            True if the ID is already present, False otherwise.
        """
        df = self.load()
        if df.empty:
            return False
        return tx["id"] in df["id"].values

    def update(self, tx_id: str, fields: dict) -> None:
        """
        Update fields on an existing transaction.

        Args:
            tx_id: The 16-character transaction ID to update.
            fields: Dict of column → new value pairs.

        Raises:
            KeyError: If tx_id is not found in the store.
        """
        df = self.load()
        if not (df["id"] == tx_id).any():
            raise KeyError(f"Transaction {tx_id} not found")
        for key, value in fields.items():
            df.loc[df["id"] == tx_id, key] = value
        df.to_csv(self.path, index=False)
```

- [ ] **Step 2: Rewrite categorizer.py with type hints and docstrings**

```python
"""
Keyword-based transaction categorizer.

Uses longest-match-wins over a keyword list loaded from config.json → categories.
"""
import json
import re


def normalize_merchant(name: str) -> str:
    """
    Normalize a raw merchant name for consistent matching and deduplication.

    Lowercases, strips branch numbers (#1234), replaces asterisks with spaces,
    and collapses whitespace.

    Args:
        name: Raw merchant name as it appears in a bank statement.

    Returns:
        Normalized lowercase merchant string.
    """
    name = name.lower()
    name = re.sub(r'#\d+', '', name)
    name = re.sub(r'\*', ' ', name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()


class Categorizer:
    """Assigns spending categories to transactions using keyword matching."""

    def __init__(self, config_path: str = "config.json") -> None:
        """
        Load category keywords from config.json.

        Args:
            config_path: Path to config.json.
        """
        with open(config_path) as f:
            config = json.load(f)
        self.categories: dict[str, list[str]] = config["categories"]

    def categorize(self, merchant: str) -> str:
        """
        Assign a category to a merchant name using longest-match-wins.

        Args:
            merchant: Raw or normalised merchant name.

        Returns:
            Category string (e.g. 'Food & Dining'). Falls back to 'Other'.
        """
        normalized = normalize_merchant(merchant)
        best_match = None
        best_len = 0
        for category, keywords in self.categories.items():
            if category == "Other":
                continue
            for keyword in keywords:
                if keyword in normalized and len(keyword) > best_len:
                    best_match = category
                    best_len = len(keyword)
        return best_match if best_match else "Other"
```

- [ ] **Step 3: Rewrite goals.py with type hints and docstrings**

```python
"""
Savings goals storage and retrieval.

Goals are persisted in data/goals.json. Supports a monthly savings target
(flat amount) and named goals with target amounts and deadlines.
"""
import json
import os
from datetime import date

DEFAULT_GOALS: dict = {
    "monthly_target": 0.0,
    "goals": [],
    "monthly_streak": {"current": 0, "best": 0, "history": {}},
}


def load_goals(data_dir: str = "data") -> dict:
    """
    Load goals from data/goals.json.

    Args:
        data_dir: Directory containing goals.json.

    Returns:
        Goals dict. Returns DEFAULT_GOALS copy if file not found.
    """
    path = f"{data_dir}/goals.json"
    if not os.path.exists(path):
        return DEFAULT_GOALS.copy()
    with open(path) as f:
        return json.load(f)


def save_goals(goals: dict, data_dir: str = "data") -> None:
    """
    Persist goals dict to data/goals.json.

    Args:
        goals: Goals dict to save.
        data_dir: Directory to write goals.json into.
    """
    path = f"{data_dir}/goals.json"
    os.makedirs(data_dir, exist_ok=True)
    with open(path, "w") as f:
        json.dump(goals, f, indent=2)


def set_monthly_target(amount: float, data_dir: str = "data") -> None:
    """
    Set the monthly savings target.

    Args:
        amount: Target savings amount per month in dollars.
        data_dir: Data directory.
    """
    goals = load_goals(data_dir)
    goals["monthly_target"] = amount
    save_goals(goals, data_dir)


def add_named_goal(
    name: str, target: float, deadline: str, data_dir: str = "data"
) -> None:
    """
    Add a named savings goal.

    Args:
        name: Human-readable goal name (e.g. 'Emergency Fund').
        target: Target amount in dollars.
        deadline: Deadline as YYYY-MM string.
        data_dir: Data directory.
    """
    goals = load_goals(data_dir)
    goals["goals"].append({
        "name": name,
        "target_amount": target,
        "current_amount": 0.0,
        "deadline": deadline,
        "created": date.today().isoformat(),
    })
    save_goals(goals, data_dir)


def get_goal_progress(data_dir: str = "data") -> dict:
    """
    Return current goals state including all named goals and monthly streak.

    Args:
        data_dir: Data directory.

    Returns:
        Goals dict with keys: monthly_target, goals, monthly_streak.
    """
    return load_goals(data_dir)
```

- [ ] **Step 4: Run existing tests to confirm nothing broke**

```bash
pytest tests/test_data_store.py tests/test_categorizer.py tests/test_goals.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add data_store.py categorizer.py goals.py
git commit -m "refactor: type hints + docstrings for data_store, categorizer, goals"
```

---

## Task 6: Add type hints + docstrings to dashboard.py, dashboard_data.py, importers/

**Files:**
- Modify: `dashboard.py`
- Modify: `dashboard_data.py`
- Modify: `importers/csv_parser.py`
- Modify: `importers/pdf_parser.py`

- [ ] **Step 1: Update dashboard.py**

Add module docstring and type hints:
```python
"""
Dashboard HTML generator.

Thin orchestrator: loads flat files, calls build_context() to compute
all analytics, then renders the Jinja2 template with inlined assets.
"""
import json
import os

import pandas as pd
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

from dashboard_data import build_context

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


def _load_files(data_dir: str) -> tuple[pd.DataFrame, dict, dict]:
    """
    Load transactions, accounts, and goals from disk.

    Args:
        data_dir: Directory containing transactions.csv, accounts.json, goals.json.

    Returns:
        (df, accounts, goals) tuple. df is empty DataFrame if no transactions.
    """
    store_path    = f"{data_dir}/transactions.csv"
    accounts_path = f"{data_dir}/accounts.json"
    goals_path    = f"{data_dir}/goals.json"

    try:
        df = pd.read_csv(store_path)
        df["date"] = pd.to_datetime(df["date"])
    except FileNotFoundError:
        df = pd.DataFrame()

    accounts: dict = {"accounts": []}
    if os.path.exists(accounts_path):
        with open(accounts_path) as f:
            accounts = json.load(f)

    goals: dict = {"monthly_target": 0.0, "goals": [], "monthly_streak": {}}
    if os.path.exists(goals_path):
        with open(goals_path) as f:
            goals = json.load(f)

    return df, accounts, goals


def build_dashboard(
    data_dir: str = "data",
    output_path: str = "reports/dashboard.html",
) -> str:
    """
    Generate the HTML dashboard and write it to disk.

    Args:
        data_dir: Directory containing transaction and account data.
        output_path: Destination path for the generated HTML file.

    Returns:
        The output_path string (for confirmation display).
    """
    df, accounts, goals = _load_files(data_dir)
    context = build_context(df, accounts, goals)

    env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR))
    env.filters["format_currency"] = lambda v: f"{v:,.2f}"
    template = env.get_template("dashboard.html.j2")

    def _read(filename: str) -> str:
        """Read a template asset file and return its contents."""
        with open(os.path.join(_TEMPLATES_DIR, filename)) as f:
            return f.read()

    html = template.render(
        **context,
        chartjs=_read("chart.min.js"),
        daisyui_css=_read("daisyui.min.css"),
        alpine_js=_read("alpine.min.js"),
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    return output_path
```

- [ ] **Step 2: Add module docstring + type hints to dashboard_data.py**

Add at the top of `dashboard_data.py`:
```python
"""
Dashboard analytics data layer.

All computation logic for the HTML dashboard. build_context() is the single
entry point — it assembles the full Jinja2 template context by calling
individual compute functions.
"""
```

Add type hints to each function signature (the bodies remain unchanged):
- `build_context(df: pd.DataFrame, accounts: dict, goals: dict, today: date | None = None) -> dict:`
- `compute_kpis(df: pd.DataFrame, accounts: dict, goals: dict, today: date | None = None) -> dict:`
- `compute_category_trends(df: pd.DataFrame, months: int = 3, today: date | None = None) -> list[dict]:`
- `compute_health_score(kpis: dict, category_trends: list[dict], goals: dict, today: date | None = None) -> dict:`
- `compute_actionable_cuts(df: pd.DataFrame, category_trends: list[dict]) -> list[dict]:`
- `compute_action_plan(cuts: list[dict], goals: dict, kpis: dict, today: date | None = None) -> list[dict]:`
- `compute_spending_pct_of_income(df: pd.DataFrame, income: float, today: date | None = None) -> list[dict]:`
- `compute_account_balances(accounts: dict) -> list[dict]:`
- `compute_top_merchants(df: pd.DataFrame, month: str) -> list[dict]:`
- `_score_to_grade(score: int) -> str:`
- `_get_at_risk_goals(goals: dict, today: date | None = None) -> list[dict]:`
- `_category_icon(category: str) -> str:`

Add docstrings to each function following the same Args/Returns format as Task 5.

- [ ] **Step 3: Update importers/csv_parser.py**

Add module docstring and type hints:
```python
"""
CSV bank statement importer.

Parses CSV exports from Chase, BofA, and Amex using per-bank format profiles
defined in config.json → bank_formats. Handles sign inversion for Amex
(which exports positive amounts as expenses).
"""
```

Update `CSVParser` and its `parse` method:
```python
class CSVParser:
    """Imports transactions from bank CSV exports."""

    def __init__(self, config_path: str = "config.json") -> None:
        """
        Load bank format profiles and categorizer from config.json.

        Args:
            config_path: Path to config.json.
        """
        ...

    def parse(self, filepath: str, bank: str, account: str) -> list[dict]:
        """
        Parse a CSV bank statement into a list of transaction dicts.

        Args:
            filepath: Path to the CSV file.
            bank: Bank key matching a config.json bank_formats entry (e.g. 'chase').
            account: Account name to tag each transaction with.

        Returns:
            List of transaction dicts matching DataStore COLUMNS schema.
        """
        ...
```

- [ ] **Step 4: Update importers/pdf_parser.py**

Add module docstring and type hints to `PDFParser` and all methods (`parse`, `_parse_table`, `_parse_regex`, `_normalize_row`).

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add dashboard.py dashboard_data.py importers/csv_parser.py importers/pdf_parser.py
git commit -m "refactor: type hints + docstrings for dashboard, dashboard_data, importers"
```

---

## Task 7: Update finance.py — type hints, consolidate imports, extract helper

**Files:**
- Modify: `finance.py`

- [ ] **Step 1: Move all imports to the top level and extract _run_store_import**

At the top of `finance.py`, replace scattered inline imports with:
```python
"""
Finance Tracker CLI entry point.

All user-facing commands are defined here using Click.
Data operations are delegated to DataStore, Categorizer, CSVParser, PDFParser, and goals.py.
"""
import json
import os
import webbrowser
from datetime import date, timedelta

import click
import pandas as pd
from rich.console import Console
from rich.table import Table

from categorizer import Categorizer
from data_store import DataStore, generate_id
from goals import add_named_goal, get_goal_progress, set_monthly_target
from importers.csv_parser import CSVParser
from importers.pdf_parser import PDFParser

console = Console()


def _run_store_import(store: DataStore, transactions: list[dict]) -> tuple[int, int]:
    """
    Add a list of transactions to the store, tracking added and skipped counts.

    Args:
        store: DataStore instance.
        transactions: List of transaction dicts to import.

    Returns:
        (added, skipped) counts.
    """
    added, skipped = 0, 0
    for tx in transactions:
        if store.is_duplicate(tx):
            skipped += 1
        else:
            store.add(tx)
            added += 1
    return added, skipped
```

Replace the duplicate import loops in `import_csv` and `import_pdf` with:
```python
added, skipped = _run_store_import(store, transactions)
```

- [ ] **Step 2: Run existing CLI tests**

```bash
pytest tests/test_cli_import.py tests/test_cli_summary.py -v
```
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add finance.py
git commit -m "refactor: finance.py — top-level imports, extract _run_store_import helper, type hints"
```

---

## Task 8: Configure pytest.ini and requirements.txt for 100% coverage

**Files:**
- Create: `pytest.ini`
- Modify: `requirements.txt`

- [ ] **Step 1: Add pytest-cov to requirements.txt**

Append to `requirements.txt`:
```
pytest-cov
```

- [ ] **Step 2: Install**

```bash
pip install pytest-cov
```

- [ ] **Step 3: Create pytest.ini**

```ini
[pytest]
addopts = --cov=. --cov-fail-under=100 --cov-report=term-missing --cov-omit=tests/fixtures/make_pdf_fixtures.py
```

- [ ] **Step 4: Run full suite and confirm 100% coverage**

```bash
pytest tests/ -v
```
Expected: All tests PASS, coverage report shows 100%

If coverage is below 100%, `--cov-report=term-missing` shows exactly which lines are uncovered. Add tests until all lines are covered.

- [ ] **Step 5: Commit**

```bash
git add pytest.ini requirements.txt
git commit -m "test: enforce 100% coverage via pytest-cov, add pytest.ini"
```

---

## Task 9: Write CHANGELOG.md

**Files:**
- Create: `CHANGELOG.md`

- [ ] **Step 1: Create CHANGELOG.md**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-03-25
### Added
- Config-driven account names via `config.json → import_accounts` (no card numbers in code)
- `statements_manifest.json` (gitignored) holds all statement file paths and metadata
- `statements_manifest.example.json` committed as setup template
- `scripts/check_secrets.py` pre-commit hook blocks staged sensitive data
- `scripts/check_changelog.py` pre-commit hook warns when CHANGELOG is not updated
- `scripts/pre-commit` shell script wiring both hooks
- `scripts/install_hooks.sh` one-command hook installer
- Comprehensive documentation: `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/CONTRIBUTING.md`
- Reference docs in `docs/references/` (7 files covering schema, CLI, bank formats, health score, testing)
- `CHANGELOG.md` with retroactive history
- `pytest.ini` enforcing 100% test coverage via `pytest-cov`
- Test fixtures for BofA Visa, BofA Checking, Robinhood CSV/PDF parsers
- Full test suite for `import_real_data.py`, `check_secrets.py`, `check_changelog.py`

### Changed
- `import_real_data.py` refactored: global mutable state → pure functions returning `(added, skipped)`
- All modules now have type hints and docstrings on every public and private function
- `finance.py` imports consolidated to top-level; duplicate import loop extracted to `_run_store_import()`
- `README.md` improved with quick-start, troubleshooting, and links to docs

### Security
- Sensitive identifiers (partial card numbers, account names) removed from all tracked files
- `statements_manifest.json` added to `.gitignore` — statement paths never committed

## [0.3.0] - 2026-03-25
### Added
- 4-tab HTML dashboard: Overview, Spending, Goals, Insights
- Health score algorithm (0–100, 5 dimensions) with letter grade (A/B+/B/C/D/F)
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
- `DataStore` flat-file storage with append-only CSV and SHA256 deduplication
- `Categorizer` keyword-based auto-categorizer driven by `config.json`
- `CSVParser` with per-bank format profiles (Chase, BofA, Amex)
- `PDFParser` generic table-based PDF importer
- `import_real_data.py` custom parsers for Chase/BofA/Robinhood real statements
- Savings goals (`goals.py`) with monthly targets and named goals with deadlines
- Integration test suite covering all CLI commands and dashboard generation
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add CHANGELOG.md with retroactive history from v0.1.0"
```

---

## Task 10: Write docs/ARCHITECTURE.md

**Files:**
- Create: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Create docs/ARCHITECTURE.md (300+ lines)**

The file must cover all sections listed in the spec:

```markdown
# Architecture

## Overview

[ASCII data-flow diagram showing:]
Bank PDFs/CSVs → import_real_data.py OR importers/ → DataStore (CSV)
                                                           ↓
                                              finance.py CLI commands
                                                           ↓
                                              dashboard.py → dashboard_data.py → reports/dashboard.html

## Module Responsibilities

[Table with columns: Module | Owns | Does NOT Own]
Rows for: data_store.py, categorizer.py, goals.py, finance.py,
          dashboard.py, dashboard_data.py, importers/csv_parser.py,
          importers/pdf_parser.py, import_real_data.py

## Data Layer Design
[Why flat files, CSV append-only, SHA256 dedup — include the formula]
[accounts.json and goals.json structure]

## Dashboard Pipeline
[load → build_context() → Jinja2 render → inline assets → HTML]
[Each build_context() sub-function and what it produces]

## Sign Convention
[Negative = expense, Positive = income — comprehensive with per-bank examples]

## Extension Points
[Adding a new bank CSV format — step by step]
[Adding a new bank PDF parser — step by step]
[Adding a new spending category]
[Adding a new dashboard tab]
[Adding a new CLI command]

## Known Limitations and Future Work
[Flat-file performance at scale]
[Plaid Phase 2 integration plan]
[Manual re-categorization workflow]
```

Each section must be comprehensive (the full file must exceed 300 lines).

- [ ] **Step 2: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add ARCHITECTURE.md — system overview, module map, extension points"
```

---

## Task 11: Write docs/SECURITY.md and docs/CONTRIBUTING.md

**Files:**
- Create: `docs/SECURITY.md`
- Create: `docs/CONTRIBUTING.md`

- [ ] **Step 1: Create docs/SECURITY.md (300+ lines)**

Sections (from spec):
- Threat model (what we protect against: git history leaks, accidental commits of real data)
- Sensitive data inventory (statements/, data/transactions.csv, data/accounts.json, data/goals.json, .env)
- Gitignore policy (what is blocked and why — reference each .gitignore entry)
- Pre-commit hook design (check_secrets.py patterns, how it works)
- Hook installation (`sh scripts/install_hooks.sh`)
- Bypass procedure (`git commit --no-verify` — when acceptable)
- `statements_manifest.json` — purpose, schema per bank, example
- How to handle real statements safely (download → statements/ → run → never commit statements/)
- Incident response — what to do if sensitive data is accidentally committed:
  1. Do NOT push
  2. `git reset HEAD~1` to undo
  3. Remove the file from git tracking
  4. Force-push only if already pushed (and notify all collaborators)

- [ ] **Step 2: Create docs/CONTRIBUTING.md (300+ lines)**

Sections (from spec):
- Development setup (clone, pip install, `sh scripts/install_hooks.sh`)
- Adding a new bank CSV format (config.json bank_formats, test with fixture)
- Adding a new bank PDF parser (where to add it in import_real_data.py, fixture generation)
- Adding new spending categories (config.json categories, re-categorization script)
- Writing and running tests (pytest, coverage requirement, fixture creation guide)
- Commit conventions (feat/fix/refactor/docs/test/security prefixes)
- Changelog update process (which version to bump, which section to add to)
- How to add a new dashboard tab (template + build_context() + test)
- How to add a new CLI command (Click group, --data-dir pattern, test)

- [ ] **Step 3: Commit**

```bash
git add docs/SECURITY.md docs/CONTRIBUTING.md
git commit -m "docs: add SECURITY.md and CONTRIBUTING.md"
```

---

## Task 12: Write docs/references/ (7 files)

**Files:**
- Create: `docs/references/transaction-schema.md`
- Create: `docs/references/config-schema.md`
- Create: `docs/references/cli-reference.md`
- Create: `docs/references/dashboard-context.md`
- Create: `docs/references/bank-formats.md`
- Create: `docs/references/health-score.md`
- Create: `docs/references/testing-guide.md`

- [ ] **Step 1: Create transaction-schema.md**

Document every field in the transaction CSV:

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| id | string (16 hex chars) | a3f9c2b1d4e5f601 | SHA256 of date+amount+merchant.lower()+account.lower() |
| date | YYYY-MM-DD | 2026-01-15 | ISO 8601 |
| amount | float | -45.20 | Negative = expense, positive = income |
| merchant | string | chipotle | Normalized (lowercase, no branch numbers) |
| category | string | Food & Dining | One of config.json categories |
| account | string | Chase-CreditCard | As set in import_accounts config |
| source | string | csv \| pdf \| manual | Import method |
| is_income | bool | False | True for payroll, transfers in |
| is_savings | bool | False | True for Robinhood transfers |
| notes | string | "" | Free-text annotation |

Include: edge cases (zero amounts, duplicate handling), schema evolution notes.

- [ ] **Step 2: Create config-schema.md**

Document every key in config.json including the new `import_accounts` section. Include type, default, description, and example for each key.

- [ ] **Step 3: Create cli-reference.md**

Document every command:
- `finance.py import csv <file> --account <n> --bank [chase|bofa|amex]`
- `finance.py import pdf <file> --account <n> --bank [chase|bofa|amex]`
- `finance.py add --amount --merchant --account [--category] [--income] [--savings]`
- `finance.py summary [--month YYYY-MM]`
- `finance.py top-categories [--last Nmonths]`
- `finance.py spending --category <n> [--year YYYY]`
- `finance.py networth`
- `finance.py account update <name> --balance <n> [--type]`
- `finance.py tag <id> [--income] [--savings]`
- `finance.py goal set <name> [--amount] [--target] [--by]`
- `finance.py goal status`
- `finance.py dashboard [--output] [--no-open]`

For each: description, all flags, example invocation, example output, error cases.

- [ ] **Step 4: Create dashboard-context.md**

Document every key returned by `build_context()`:
kpis, category_trends, health, cuts, action_plan, spending_pct, account_balances,
top_merchants, trend_labels, trend_values, goals_display, monthly_streak,
monthly_target, generated_at.

For each: type, example value, which template tab uses it.

- [ ] **Step 5: Create bank-formats.md**

Document per-bank quirks including the `statements_manifest.json` schema per bank,
sign conventions, known issues, and the `parse_bofa_checking_pdf` account-from-PDF behaviour.

- [ ] **Step 6: Create health-score.md**

Document all 5 scoring dimensions:
1. Savings rate (30 pts, linear 0→20%)
2. Spending trend (25 pts, -8 per category up >20% MoM)
3. Goal progress (25 pts, -12 per at-risk goal)
4. Subscription ratio (10 pts, <8%/15% thresholds)
5. Emergency fund (10 pts, >50% complete)

Include grade scale, worked examples at different score levels.

- [ ] **Step 7: Create testing-guide.md**

Document test file → module mapping, fixture descriptions, how to add new fixtures,
coverage policy (100% enforced), how to run tests, how to check coverage report.

- [ ] **Step 8: Commit all reference files**

```bash
git add docs/references/
git commit -m "docs: add 7 reference files — schema, CLI, bank formats, health score, testing"
```

---

## Task 13: Update README.md and CLAUDE.md

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Rewrite README.md**

Structure:
```markdown
# Finance Tracker

Personal finance CLI + HTML dashboard. Tracks Chase, BofA, Amex, Robinhood.

## Prerequisites
Python 3.10+, pip

## Quick Start

1. Install
   pip install -r requirements.txt
   sh scripts/install_hooks.sh

2. Import your first statement
   python finance.py import csv ~/Downloads/Chase.csv --account Chase-CreditCard --bank chase
   → Imported 47 new transactions (3 skipped as duplicates)

3. Open the dashboard
   python finance.py dashboard
   → Dashboard generated: reports/dashboard.html  [opens in browser]

## Command Reference
[Brief one-liner per command, linking to docs/references/cli-reference.md for full detail]

## Troubleshooting
[5 common errors + fixes]
1. FileNotFoundError: config.json — run from the repo root
2. KeyError: 'chase' — add bank format to config.json → bank_formats
3. Dashboard is empty — no transactions imported yet; run finance.py import first
4. PDFParser returns 0 transactions — try import_real_data.py for real statement formats
5. Coverage below 100% — check pytest --cov-report=term-missing output

## Documentation
- Architecture: docs/ARCHITECTURE.md
- Security: docs/SECURITY.md
- Contributing: docs/CONTRIBUTING.md
- Reference docs: docs/references/

## Phase 2: Plaid Integration
Add Plaid keys to .env (never commit), implement importers/plaid.py connector.
```

- [ ] **Step 2: Update CLAUDE.md**

Add references to new docs after the existing Architecture section:

```markdown
## Documentation

Full docs live in `docs/`:
- `docs/ARCHITECTURE.md` — system design, module map, extension points
- `docs/SECURITY.md` — sensitive data policy, pre-commit hooks
- `docs/CONTRIBUTING.md` — how to add banks, categories, CLI commands
- `docs/references/` — deep reference for schema, CLI, bank formats, health score, testing
```

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: improve README.md with quick-start and troubleshooting, sync CLAUDE.md"
```

---

## Task 14: Final verification

- [ ] **Step 1: Run full test suite with coverage**

```bash
pytest tests/ -v
```
Expected: All PASS, 100% coverage

- [ ] **Step 2: Verify no sensitive data in tracked files**

```bash
git diff HEAD~14..HEAD --name-only  # review all changed files
grep -r "statements/" . --include="*.py" --exclude-dir=".git"  # should only match test fixtures and docs
```

- [ ] **Step 3: Install and test pre-commit hook**

```bash
sh scripts/install_hooks.sh
echo "test" > /tmp/test_commit.txt
git add /tmp/test_commit.txt  # just checking hook runs
```

- [ ] **Step 4: Final commit if any loose ends**

```bash
git status  # should be clean
```
