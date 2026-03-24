# Finance Tracker — Design Spec
**Date:** 2026-03-24
**Status:** Approved

---

## Overview

A personal finance CLI tool with an auto-generated HTML dashboard. Tracks spending across Chase, BofA, Amex, and Robinhood. Helps identify where money is going, suggests cuts, and tracks savings goals. Built in Python, data stored as flat files.

---

## Goals

1. Pull and consolidate transactions from Chase, BofA, Amex (PDF/CSV import → Plaid API in Phase 2)
2. Auto-categorize spending and surface top categories
3. Track net worth including Robinhood balance
4. Set and track savings goals (monthly rate + named targets)
5. Generate a single-file HTML dashboard with charts and insights

---

## Architecture

### Platform
- **CLI** (`finance.py`) — all interactions via terminal commands, built with `click`
- **Dashboard** — static `reports/dashboard.html` generated on demand, opened in browser

### Storage (Flat-File)
All data lives as plain files — no database required.

```
finance-tracker/
├── finance.py              # CLI entry point (click)
├── importers/
│   ├── pdf_parser.py       # Parse Chase/BofA/Amex PDF statements (pdfplumber)
│   ├── csv_parser.py       # Parse exported CSVs (pandas) with per-bank format profiles
│   └── plaid.py            # Phase 2: Plaid API connector
├── data/
│   ├── transactions.csv    # Master transaction ledger (append-only)
│   ├── accounts.json       # Account balances + metadata
│   └── goals.json          # Savings goals + monthly targets
├── reports/
│   └── dashboard.html      # Generated HTML dashboard (Chart.js bundled inline)
├── categorizer.py          # Keyword-based auto-categorizer
├── dashboard.py            # HTML report generator (Jinja2 + Chart.js inline)
├── config.json             # Account names, categories, bank format profiles
├── .env                    # Plaid API keys (Phase 2) — gitignored
├── requirements.txt
└── README.md
```

### Transaction Schema (`transactions.csv`)
| Field | Type | Example |
|-------|------|---------|
| id | string (SHA256 hash of date+amount+merchant+account) | a3f9c2... |
| date | YYYY-MM-DD | 2024-01-15 |
| amount | float (negative = expense) | -45.20 |
| merchant | string (normalized) | Chipotle |
| category | string | Food & Dining |
| account | string | Chase-Checking |
| source | enum: csv, pdf, manual, plaid | csv |
| is_income | bool | False |
| is_savings | bool | False |
| notes | string | "" |

**Deduplication:** Transactions are matched on `date + amount + normalized_merchant + account`. Merchant names are normalized before matching (stripped of branch suffixes like `#1234`, lowercased, whitespace-collapsed). When a potential duplicate is detected, the user is prompted to confirm rather than silently dropping it — this handles the edge case of two identical charges on the same day.

### `goals.json` Schema
```json
{
  "monthly_target": 500.00,
  "goals": [
    {
      "name": "Emergency Fund",
      "target_amount": 10000.00,
      "current_amount": 6200.00,
      "deadline": "2025-06",
      "created": "2024-01-01"
    }
  ],
  "monthly_streak": {
    "current": 3,
    "best": 7,
    "history": {"2024-01": true, "2024-02": true, "2024-03": false}
  }
}
```

### `accounts.json` Schema
```json
{
  "accounts": [
    {
      "name": "Chase-Checking",
      "type": "checking",
      "institution": "Chase",
      "balance": 4200.00,
      "currency": "USD",
      "last_updated": "2024-01-15"
    },
    {
      "name": "Robinhood",
      "type": "investment",
      "institution": "Robinhood",
      "balance": 12500.00,
      "currency": "USD",
      "last_updated": "2024-01-15"
    }
  ]
}
```

### Bank CSV Format Profiles
Each bank exports CSVs with different column names and sign conventions. Format profiles in `config.json` map each bank's columns to the normalized transaction schema:

```json
{
  "bank_formats": {
    "chase": {
      "date_col": "Transaction Date",
      "amount_col": "Amount",
      "merchant_col": "Description",
      "amount_sign": "standard"
    },
    "bofa": {
      "date_col": "Date",
      "amount_col": "Amount",
      "merchant_col": "Description",
      "amount_sign": "standard"
    },
    "amex": {
      "date_col": "Date",
      "amount_col": "Amount",
      "merchant_col": "Description",
      "amount_sign": "inverted"
    }
  }
}
```
`amount_sign: "inverted"` flips the sign on import (Amex exports charges as positive numbers).

### PDF Parsing Strategy
PDF parsing uses `pdfplumber` with per-bank submodules in `importers/pdf_parser.py`. Each bank's statement has a recognizable layout:
- **Table detection** (Chase, BofA): `pdfplumber.extract_table()` on statement pages
- **Line-by-line regex** (Amex): regex patterns matching date + amount + description per line

The import command requires `--account` to identify which bank parser to use. Unknown formats fall back to table detection with a warning.

---

## Features

### Phase 1 — Core (CSV/PDF Import)

**Data Import**
- `python finance.py import pdf <file> --account <name>` — parse PDF bank statement
- `python finance.py import csv <file> --account <name>` — parse CSV export
- `python finance.py add --amount <n> --merchant <name> --category <cat>` — manual entry

**Spending Analysis**
- `python finance.py summary --month YYYY-MM` — income vs expenses for a month
- `python finance.py top-categories --last <N>months` — ranked spending by category
- `python finance.py spending --category <cat> --year YYYY` — drill into a category

**Net Worth**
- `python finance.py networth` — sum of all account balances (Chase + BofA + Amex + Robinhood)
- Robinhood: manual balance entry in Phase 1, API in Phase 2

**Savings Goals**
- `python finance.py goal set monthly --amount <n>` — monthly savings target
- `python finance.py goal set "<name>" --target <n> --by YYYY-MM` — named goal
- `python finance.py goal status` — progress on all goals

**Dashboard**
- `python finance.py dashboard` — generates `reports/dashboard.html` and opens in browser
- Sections: Net Worth, Monthly Savings vs Target, Top Categories (bar chart), Goal Progress, Month-over-Month trends, Insights callouts

**Account Balance Update**
- `python finance.py account update <name> --balance <n>` — manually update an account balance (used for Robinhood in Phase 1)

### Phase 2 — Plaid Integration
- Connect Chase, BofA, Amex, Robinhood via Plaid Link
- `python finance.py sync` — pull latest transactions from all accounts automatically
- Robinhood balance pulled via Plaid (portfolio value)
- Same flat-file storage — Plaid just becomes another import source

---

## Auto-Categorization

Keyword matching on merchant name → category mapping in `config.json`.

Default categories:
- Food & Dining (Chipotle, McDonald's, DoorDash, Uber Eats, restaurants)
- Transport (Uber, Lyft, gas stations, parking)
- Subscriptions (Netflix, Spotify, Adobe, Apple, Amazon Prime)
- Shopping (Amazon, Target, Walmart, clothing)
- Health (pharmacy, doctors, gyms)
- Income (payroll, transfers in)
- Investments (Robinhood transfers)
- Other (uncategorized fallback)

Users can add keywords to `config.json` to improve categorization.

---

## Savings Goals Logic

- **Monthly rate:** At month-end, compute `income - expenses`. Income = transactions where `is_income=True`. Expenses = all negative-amount transactions excluding savings transfers. Compare result to monthly target. Record hit/miss streak.
- **Income tagging:** Income transactions are auto-detected by category ("Income") but the user can manually flag any transaction as income using `python finance.py tag <transaction_id> --income`. This handles edge cases like ACH transfers and Zelle payments that may not match keyword patterns.
- **Named goals:** User sets target amount + deadline. System calculates required monthly contribution. Contributions are tracked via transactions where `is_savings=True`, set manually with `python finance.py tag <transaction_id> --savings` or at import time with `--savings` flag.
- Monthly savings can be auto-allocated toward named goals proportionally.

---

## Dashboard Design

Single self-contained HTML file — Chart.js is bundled inline (no CDN dependency, works offline):

1. **Header** — Net Worth (total across all accounts), date last updated
2. **This Month** — Income, Expenses, Saved (vs monthly goal)
3. **Spending by Category** — horizontal bar chart, current month vs last month
4. **Top Merchants** — table of top 10 merchants by spend this month
5. **Goal Progress** — progress bars for each named goal + monthly streak
6. **Trends** — line chart of monthly spending over last 12 months
7. **Insights** — auto-generated text callouts based on these specific rules:
   - Category with largest month-over-month % increase (threshold: >15%)
   - Top spending category this month
   - Monthly savings goal: on track / missed / exceeded
   - Any named goal that will be missed at current pace
   - Largest single transaction this month
   - Subscription cost total (all "Subscriptions" category transactions)

---

## README

The README will include:
- Prerequisites (Python 3.10+, pip)
- Installation steps (`pip install -r requirements.txt`)
- Quick start guide (import first statement, run dashboard)
- Full CLI command reference
- How to add new bank CSV formats
- Phase 2 Plaid setup guide

---

## Tech Stack

| Concern | Library |
|---------|---------|
| CLI | `click` |
| PDF parsing | `pdfplumber` |
| CSV/data | `pandas` |
| Terminal output | `rich` |
| Dashboard templating | `Jinja2` |
| Charts | `Chart.js` (bundled inline in dashboard HTML) |
| Plaid (Phase 2) | `plaid-python` |

---

## Out of Scope

- Multi-user support
- Budget planning / envelope budgeting
- Deep investment analytics (just balance + cash flow for Robinhood)
- Mobile app
- Cloud sync
