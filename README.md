# Finance Tracker

A personal finance CLI with an auto-generated HTML dashboard. Tracks spending across Chase, BofA, Amex, and Robinhood using flat-file storage — no database, no cloud sync, no accounts.

---

## Prerequisites

- Python 3.10+
- pip

## Installation

```bash
git clone <repo>
cd finance-tracker
pip install -r requirements.txt
```

Install the pre-commit hooks (recommended):

```bash
bash scripts/install_hooks.sh
```

The hooks warn when commits lack a CHANGELOG entry and block commits that contain account numbers, card numbers, or other sensitive data patterns.

---

## Quick Start

### 1. Import your first bank statement

Download a CSV from your bank's website, then:

```bash
# Chase
python3 main.py import csv ~/Downloads/Chase_Activity.csv \
  --account Chase-CreditCard --bank chase

# Bank of America
python3 main.py import csv ~/Downloads/BoA_Activity.csv \
  --account BofA-Checking --bank bofa

# Amex (sign is inverted automatically)
python3 main.py import csv ~/Downloads/Amex_Activity.csv \
  --account Amex-Credit --bank amex
```

PDF statements also work for simple table-format files:

```bash
python3 main.py import pdf ~/Downloads/Chase_Statement.pdf \
  --account Chase-CreditCard --bank chase
```

For real Chase, BofA, and Robinhood statements (text-layout PDFs), use `python3 -m importers.real_data` instead — see [docs/references/bank-formats.md](docs/references/bank-formats.md).

### 2. Update account balances

```bash
python3 main.py account update Chase-CreditCard --balance -987.43 --type credit
python3 main.py account update BofA-Checking --balance 4200.00 --type checking
python3 main.py account update Robinhood --balance 12500.00 --type investment
```

### 3. Open the dashboard

```bash
python3 main.py dashboard
```

The HTML report opens automatically in your default browser. To generate without opening:

```bash
python3 main.py dashboard --no-open
```

---

## Command Reference

### Import

```bash
python3 main.py import csv <file> --account <name> --bank [chase|bofa|amex]
python3 main.py import pdf <file> --account <name> --bank [chase|bofa|amex]
```

### Manual Entry

```bash
python3 main.py add --amount -45.20 --merchant "Chipotle" --account Chase-CreditCard
python3 main.py add --amount 2500.00 --merchant "Payroll" --account BofA-Checking --income
python3 main.py add --amount -500.00 --merchant "Robinhood" --account BofA-Checking --savings
```

### Analysis

```bash
python3 main.py summary                         # This month
python3 main.py summary --month 2026-01         # Specific month
python3 main.py top-categories                  # Top spending categories (last month)
python3 main.py top-categories --last 3months   # Last 3 months
python3 main.py spending --category "Food & Dining"
python3 main.py spending --category Subscriptions --year 2026
```

### Net Worth

```bash
python3 main.py networth
python3 main.py account update Robinhood --balance 13500.00 --type investment
```

### Savings Goals

```bash
python3 main.py goal set monthly --amount 500
python3 main.py goal set "Emergency Fund" --target 10000 --by 2026-12
python3 main.py goal status
```

### Tagging

```bash
python3 main.py tag <transaction_id> --income    # Mark as income
python3 main.py tag <transaction_id> --savings   # Mark as savings transfer
```

Full option documentation: [docs/references/cli-reference.md](docs/references/cli-reference.md)

---

## Running Tests

```bash
# All tests with coverage (enforces 100%)
pytest

# Specific file
pytest tests/test_dashboard_data.py -v

# Without coverage (faster during development)
pytest -p no:cov
```

See [docs/references/testing-guide.md](docs/references/testing-guide.md) for patterns and fixture details.

---

## Troubleshooting

**`KeyError` on import CSV:** The CSV column headers don't match the bank format config. Check `config.json → bank_formats` for the expected column names, or run `head -1 yourfile.csv` to see actual headers.

**Transaction already exists, skipped:** The transaction was already imported. Deduplication is based on date + amount + merchant + account.

**Dashboard shows $0 net worth:** No `data/accounts.json` found. Run `python3 main.py account update <name> --balance <n>` for each account.

**Dashboard shows no goals:** No `data/goals.json` found. Run `python3 main.py goal set monthly --amount 500` to create it.

**PDF import returns 0 transactions:** The PDF uses a text-layout format that `pdfplumber.extract_table()` can't parse. Use `python3 -m importers.real_data` instead. See [docs/references/bank-formats.md](docs/references/bank-formats.md).

**`importers/real_data.py` fails with `FileNotFoundError: statements_manifest.json`:** Copy `statements_manifest.example.json` to `statements_manifest.json` and fill in the file paths for your statements.

---

## Security

Statement files and transaction data are gitignored. The pre-commit hook in `scripts/check_secrets.py` blocks commits containing account numbers, card numbers (4×4 digit groups), SSN patterns, and hardcoded file paths to common sensitive directories.

See [docs/SECURITY.md](docs/SECURITY.md) for the full policy.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data flow, module responsibilities |
| [docs/SECURITY.md](docs/SECURITY.md) | Security policy, what is gitignored, pre-commit hooks |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Development workflow, TDD, adding banks/categories |
| [docs/references/cli-reference.md](docs/references/cli-reference.md) | Full CLI option reference |
| [docs/references/transaction-schema.md](docs/references/transaction-schema.md) | Transaction CSV schema, deduplication |
| [docs/references/config-schema.md](docs/references/config-schema.md) | config.json schema, bank formats, categories |
| [docs/references/bank-formats.md](docs/references/bank-formats.md) | Per-bank format details, adding new banks |
| [docs/references/dashboard-context.md](docs/references/dashboard-context.md) | Dashboard template context dict reference |
| [docs/references/health-score.md](docs/references/health-score.md) | Health score dimensions and scoring algorithm |
| [docs/references/testing-guide.md](docs/references/testing-guide.md) | Test structure, fixtures, coverage requirements |
