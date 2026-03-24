# Architecture Reference

This document describes the design, data flow, module responsibilities, and
extension points for the personal finance tracker. It is intended for
contributors who need to understand how the system fits together before
making changes.

---

## 1. Overview

The finance tracker is a local-first, single-user Python application. There
are no servers, no databases, and no external services required. Everything
lives in flat files on disk.

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INPUT SOURCES                               │
│                                                                     │
│  Bank PDFs / CSVs         Real statement files (gitignored)         │
│  (sample / test data)     (Chase, BofA, Robinhood)                  │
└────────┬──────────────────────────────┬────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌────────────────────────┐
│  importers/     │          │  import_real_data.py   │
│  csv_parser.py  │          │                        │
│  pdf_parser.py  │          │  parse_chase_pdf()     │
│                 │          │  parse_bofa_credit_pdf()
│  Generic table- │          │  parse_bofa_checking_  │
│  based parsing  │          │    pdf()               │
│  + bank format  │          │  parse_robinhood_csv() │
│  profiles from  │          │  parse_robinhood_pdf() │
│  config.json    │          │                        │
└────────┬────────┘          └────────────┬───────────┘
         │                               │
         │     Both paths call           │
         └──────────────┬────────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │   DataStore      │   data/transactions.csv
              │  (data_store.py) │◄──────────────────────
              │                  │   SHA256 deduplication
              │  add()           │   Append-only CSV
              │  is_duplicate()  │
              │  update()        │
              └────────┬─────────┘
                       │
         ┌─────────────┼──────────────┐
         │             │              │
         ▼             ▼              ▼
┌──────────────┐ ┌──────────┐ ┌────────────────┐
│ finance.py   │ │goals.py  │ │ categorizer.py │
│ CLI commands │ │          │ │                │
│              │ │ goals.   │ │ Categorizer    │
│ summary      │ │  json    │ │ .categorize()  │
│ spending     │ │          │ │                │
│ networth     │ │ monthly  │ │ keyword match  │
│ top-cats     │ │ _target  │ │ on normalized  │
│ import csv   │ │ named    │ │ merchant name  │
│ import pdf   │ │  goals   │ │                │
│ goal set     │ │ streak   │ └────────────────┘
│ goal status  │ └──────────┘
│ tag          │
│ account      │
│  update      │
│ dashboard    │
└──────┬───────┘
       │  finance.py dashboard command calls
       ▼
┌─────────────────┐
│  dashboard.py   │   (thin renderer / orchestrator)
│                 │
│ build_dashboard()
│  _load_files()  │──► data/transactions.csv
│                 │──► data/accounts.json
│                 │──► data/goals.json
└────────┬────────┘
         │  passes DataFrames + dicts to
         ▼
┌─────────────────────────────────────────────────────┐
│  dashboard_data.py                                  │
│                                                     │
│  build_context(df, accounts, goals, today)          │
│    compute_kpis()                                   │
│    compute_category_trends()                        │
│    compute_health_score()                           │
│    compute_actionable_cuts()                        │
│    compute_action_plan()                            │
│    compute_spending_pct_of_income()                 │
│    compute_account_balances()                       │
│    compute_top_merchants()                          │
│    [inline: 12-month trend + goals_display]         │
└────────┬────────────────────────────────────────────┘
         │  returns context dict to dashboard.py
         ▼
┌─────────────────────────────────────────────────────┐
│  Jinja2 rendering                                   │
│                                                     │
│  templates/dashboard.html.j2                        │
│    + templates/chart.min.js    (inlined)            │
│    + templates/daisyui.min.css (inlined)            │
│    + templates/alpine.min.js   (inlined)            │
└────────┬────────────────────────────────────────────┘
         │  written to
         ▼
┌─────────────────────┐
│  reports/           │
│  dashboard.html     │  Zero external dependencies
│                     │  Works fully offline
└─────────────────────┘
```

### Key Design Principles

1. **No external services.** All data stays on the local machine.
2. **Flat files only.** CSV for transactions, JSON for accounts and goals.
3. **Idempotent imports.** Re-running an import never creates duplicates.
4. **Offline dashboard.** The HTML report has all JS and CSS inlined.
5. **Thin CLI.** `finance.py` orchestrates; analytics live in `dashboard_data.py`.

---

## 2. Module Responsibility Table

| Module | Owns | Does NOT Own |
|---|---|---|
| `data_store.py` | Transaction persistence; deduplication via SHA256 ID; CSV read/write; `add()`, `update()`, `load()`, `is_duplicate()` | Categorization; bank-specific parsing; analytics |
| `categorizer.py` | Keyword matching against normalized merchant names; merchant normalization (`normalize_merchant()`); `categorize()` returning a category string | File I/O; transaction storage; any DataFrame operations |
| `goals.py` | `goals.json` read/write; `monthly_target` field; named goals list; `monthly_streak` tracker; `add_named_goal()`, `set_monthly_target()`, `get_goal_progress()` | Goal progress calculations (those live in `dashboard_data.py`); rendering |
| `finance.py` | CLI commands (`@cli.command`); user-facing Rich console output; orchestration of imports, summaries, and goal operations | Analytics computation; data storage logic; HTML rendering |
| `dashboard.py` | Jinja2 template rendering; file I/O for inlined assets (chart.min.js, daisyui.min.css, alpine.min.js); writing `reports/dashboard.html`; `_load_files()` helper | Analytics; any computation on transaction data |
| `dashboard_data.py` | All analytics computation; the `build_context()` output dict; every `compute_*` sub-function | Rendering; file I/O; CLI output |
| `importers/csv_parser.py` | CSV format profiles loaded from `config.json → bank_formats`; per-bank column mapping (date, amount, merchant columns); Amex sign inversion | Storage; writing to DataStore directly (returns a list of dicts to the caller) |
| `importers/pdf_parser.py` | Generic table-based PDF parsing via pdfplumber; regex line parsing for Amex; `_normalize_row()` helper | Real bank statement parsing (that is `import_real_data.py`'s domain); storage |
| `import_real_data.py` | Real bank statement parsing for Chase credit, BofA Visa, BofA checking/savings, Robinhood CSV, Robinhood brokerage PDF; `run_import()` entry point reading `statements_manifest.json` | Storage logic beyond calling `DataStore.add()`; categorization beyond delegating to `Categorizer` |

---

## 3. Data Layer Design

### Why Flat Files

The system uses flat CSV and JSON files instead of a database. The reasons are:

- **No dependencies.** A SQLite database requires the `sqlite3` module;
  PostgreSQL requires a running server. Flat files require nothing beyond the
  standard library and pandas.
- **Inspectability.** Any user can open `transactions.csv` in a spreadsheet
  and understand or edit their data without special tools.
- **Portability.** The entire data set is a handful of files that can be
  moved, backed up, or version-controlled with `git`.
- **Sufficient scale.** A personal finance tracker processes thousands of
  transactions per year, not millions. Pandas handles a CSV of 50 000 rows
  with sub-second latency on any modern laptop.

### Append-Only CSV

`DataStore.add()` loads the existing CSV, appends one row via
`pd.concat()`, and writes the entire file back. There are no in-place edits
to existing rows except through `DataStore.update()`, which rewrites the
file after modifying the target row.

The CSV columns are, in order:

```
id | date | amount | merchant | category | account | source | is_income | is_savings | notes
```

### SHA256 Deduplication

Every transaction is assigned a stable, deterministic ID before being
stored. The ID is computed as:

```python
raw = f"{date}{amount}{merchant.lower().strip()}{account.lower().strip()}"
id  = hashlib.sha256(raw.encode()).hexdigest()[:16]
```

Because the ID depends only on the transaction's content (not a sequence
number or timestamp), re-importing the same statement file produces the same
IDs. `DataStore.is_duplicate()` checks whether the ID already exists in the
CSV and skips the row if so. This means:

- Importing the same PDF twice is safe — duplicates are silently skipped.
- Importing overlapping date ranges across multiple statements is safe.
- Manual additions with the same date, amount, merchant, and account are
  deduplicated automatically.

### accounts.json

Stores account names, types, balances, and metadata. Structure:

```json
{
  "accounts": [
    {
      "name": "Chase-CreditCard",
      "type": "credit",
      "institution": "Chase",
      "balance": -1234.56,
      "currency": "USD",
      "last_updated": "2026-03-01"
    }
  ]
}
```

Balances are updated manually or via `finance.py account update <name> --balance <n>`.
Net worth is the sum of all account balances (credit card balances are
negative, so they reduce net worth correctly).

### goals.json

Stores the monthly savings target, a list of named goals, and the monthly
savings streak tracker. Structure:

```json
{
  "monthly_target": 1500.0,
  "monthly_streak": {
    "current": 3,
    "best": 7,
    "history": {"2026-01": true, "2026-02": true, "2026-03": true}
  },
  "goals": [
    {
      "name": "Emergency Fund",
      "target_amount": 10000.0,
      "current_amount": 4200.0,
      "deadline": "2026-12",
      "created": "2026-01-01"
    }
  ]
}
```

Goal progress calculation (expected vs actual percentage based on elapsed
time) is performed in `dashboard_data.py`, not in `goals.py`.

### Sign Convention

**Negative = expense (money leaving); Positive = income (money arriving).**

This matches standard accounting (double-entry bookkeeping) convention:
a debit to your checking account is negative.

Amex CSVs invert this convention — a positive number in their export means
money was spent. `CSVParser` handles this: when `config.json → bank_formats
→ amex → amount_sign` is `"inverted"`, the raw amount is negated before
being stored.

```python
amount = -raw_amount if fmt["amount_sign"] == "inverted" else raw_amount
```

All other supported banks (Chase, BofA) use `"standard"` sign convention
and require no adjustment.

---

## 4. Dashboard Pipeline

The dashboard is built end-to-end by calling `finance.py dashboard`, which
calls `build_dashboard()` in `dashboard.py`.

### Step-by-Step

**Step 1 — Load data files.**
`build_dashboard()` calls `_load_files(data_dir)`. This function reads:

- `data/transactions.csv` → pandas DataFrame with a parsed `date` column
- `data/accounts.json` → Python dict
- `data/goals.json` → Python dict

If any file is missing, a safe empty default is returned (empty DataFrame,
empty accounts dict, default goals dict). The dashboard renders correctly
with empty data.

**Step 2 — Build the context dict.**
`build_dashboard()` passes the three data objects to `build_context()` in
`dashboard_data.py`. `build_context()` calls nine compute functions
(described below) and assembles all results into a single flat Python dict.
It also computes the 12-month spending trend and the goals display list
inline before returning.

**Step 3 — Render the Jinja2 template.**
`dashboard.py` creates a Jinja2 `Environment` pointing at the `templates/`
directory and loads `dashboard.html.j2`. It registers a `format_currency`
filter (`{v:,.2f}`). The template is rendered with `**context` unpacked as
template variables.

**Step 4 — Inline static assets.**
Three asset files are read from `templates/` and passed to the template as
string variables:

- `chart.min.js` → `chartjs`
- `daisyui.min.css` → `daisyui_css`
- `alpine.min.js` → `alpine_js`

The template embeds them inside `<script>` and `<style>` tags. The final
HTML has zero `<link>` or `<script src>` references to external URLs.

**Step 5 — Write output.**
The rendered HTML string is written to `reports/dashboard.html`. The
`reports/` directory is created if it does not exist.

**Step 6 — Open in browser.**
Unless `--no-open` is passed, `webbrowser.open()` opens the file in the
default system browser using a `file://` URL.

### The Nine build_context Sub-Functions

| Function | Returns | Description |
|---|---|---|
| `compute_kpis(df, accounts, goals, today)` | dict | Current-month income, expenses, amount saved, savings rate, net worth, monthly target. All values are rounded to 2 decimal places. |
| `compute_category_trends(df, months=3, today)` | list of dicts | For each spending category: current-month total, prior-month totals, percentage change, and direction label (`up`/`down`/`flat`). Threshold for non-flat is ±5%. |
| `compute_health_score(kpis, category_trends, goals)` | dict | Overall score (0–100), letter grade, list of passing dimensions, list of failing dimensions. See Section 5 for the full algorithm. |
| `compute_actionable_cuts(df, category_trends)` | list of dicts | Spending reduction opportunities sorted by potential monthly saving. Subscriptions are broken out per-merchant (≥$15/mo). Other categories are flagged if current spend exceeds 3-month average by more than 15%. Transport gets a ride-frequency check. |
| `compute_action_plan(cuts, goals, kpis, today)` | list of dicts | Up to 3 prioritized action steps, one per month, derived from the top cuts. The first step is linked to the highest-priority at-risk goal if one exists. |
| `compute_spending_pct_of_income(df, income, today)` | list of dicts | Each expense category as a percentage of this month's income, sorted descending by amount. Used in the spending breakdown tab. |
| `compute_account_balances(accounts)` | list of dicts | Each account with its balance, type, and share of total positive assets. Used in the accounts tab. |
| `compute_top_merchants(df, month)` | list of dicts | Top 10 merchants by spend for the given month, with transaction count and category. |
| 12-month trend (inline) | trend_labels, trend_values | Computed inline in `build_context()`. Iterates 12 months back from today, summing absolute expense amounts per month. Used to draw the spending history chart. |

Additionally, `build_context()` builds `goals_display` inline — a list of
dicts with `name`, `pct`, `current`, `target`, `deadline`, `created` — for
the Goals tab.

---

## 5. Health Score Algorithm

The financial health score is computed by `compute_health_score()` in
`dashboard_data.py`. The total is out of 100 points across 5 dimensions.
Partial credit is applied continuously where noted.

### Dimension 1 — Savings Rate (30 points)

```
savings_pts = min(savings_rate / 0.20, 1.0) * 30
```

This is a linear scale from 0% to 20% savings rate. Saving exactly 20% of
income or more earns the full 30 points. Saving 10% earns 15 points. Saving
0% earns 0 points.

A savings rate of 20% is used as the reference because it aligns with common
personal finance guidance (the 50/30/20 rule).

The dimension is marked **passing** if `savings_pts >= 25` (i.e., savings
rate >= ~16.7%).

### Dimension 2 — Spending Trend (25 points)

```
offending = [t for t in category_trends if t["pct_change"] > 0.20]
trend_pts = max(0.0, 25.0 - len(offending) * 8)
```

Each spending category that is more than 20% higher than the prior month
deducts 8 points. Three or more offending categories brings this dimension
to zero. If no categories are up more than 20% month-over-month, the full
25 points are awarded and the dimension is marked **passing**.

### Dimension 3 — Goal Progress (25 points)

```
goal_pts = max(0.0, 25.0 - len(at_risk_goals) * 12)
```

A goal is **at-risk** when the actual percentage complete is less than the
expected percentage complete given elapsed time since goal creation. For
example, if a goal was created 6 months ago and has a 12-month deadline,
the expected completion is 50%. If only 30% of the target has been saved,
the goal is at-risk.

Each at-risk goal deducts 12 points. Two or more at-risk goals reduces this
dimension to zero. If all goals are on track, the full 25 points are awarded.

### Dimension 4 — Subscription Ratio (10 points)

```
sub_ratio = subscriptions_this_month / income_this_month
```

- `sub_ratio < 0.08` (less than 8% of income) → full 10 points, marked passing
- `0.08 <= sub_ratio <= 0.15` → 5 points
- `sub_ratio > 0.15` → 0 points, marked failing

### Dimension 5 — Emergency Fund (10 points)

The system looks for a goal whose name contains the word "emergency"
(case-insensitive).

- Emergency fund goal >= 50% complete → full 10 points, marked passing
- Emergency fund goal < 50% complete → 0 points, marked failing
- No emergency fund goal defined → 5 points (partial credit; not marked
  as failing to avoid alarming users who haven't set up the goal yet)

### Grade Scale

| Score | Grade |
|---|---|
| 90 – 100 | A |
| 80 – 89 | B+ |
| 75 – 79 | B |
| 60 – 74 | C |
| 45 – 59 | D |
| < 45 | F |

Note: The actual thresholds in `_score_to_grade()` are 90, 80, 75, 60, 45.
The task specification lists 70 and 50 as B/D boundaries, but the code uses
75 and 45. The code is authoritative.

---

## 6. Extension Points

### Adding a New Bank CSV Format

The CSV importer is driven entirely by `config.json`. No code changes are
required to add a new bank.

1. Open `config.json` and add a new entry under `bank_formats`:

   ```json
   "newbank": {
     "date_col": "Posted Date",
     "amount_col": "Transaction Amount",
     "merchant_col": "Payee",
     "amount_sign": "standard"
   }
   ```

   Set `amount_sign` to `"inverted"` if the bank exports positive numbers
   for expenses (as Amex does). Use `"standard"` otherwise.

2. Test the import with a sample file:

   ```
   python finance.py import csv sample.csv --bank newbank --account MyAccount
   ```

3. Add a fixture CSV file to `tests/fixtures/` named
   `newbank_sample.csv` with a few representative rows covering both
   expenses and credits.

4. Add a test case to `tests/test_csv_parser.py` that asserts the correct
   number of transactions are parsed, amounts have the correct sign, and
   merchants are normalized.

### Adding a New Bank PDF Parser (Real Statement Format)

Real bank PDFs require a custom parser function because statement layouts
vary significantly between institutions.

1. Add a parser function to `import_real_data.py`:

   ```python
   def parse_newbank_pdf(
       store: DataStore,
       cat: Categorizer,
       filepath: str,
       account: str,
   ) -> tuple[int, int]:
       """Parse a NewBank PDF statement. Returns (added, skipped)."""
       added, skipped = 0, 0
       # ... parse logic using pdfplumber ...
       a, s = _add_tx(store, cat, date_str, amount, merchant, account)
       added += a; skipped += s
       return added, skipped
   ```

   Use `_add_tx()` for every transaction — it normalizes the merchant,
   calls `Categorizer.categorize()`, generates the SHA256 ID, and handles
   deduplication.

2. Add the new bank key to `statements_manifest.example.json`:

   ```json
   "newbank": [
     {"path": "statements/newbank/2026-01.pdf"}
   ]
   ```

   Users copy this file to `statements_manifest.json` (which is gitignored)
   and fill in their real paths.

3. Add the account name to `config.json → import_accounts`:

   ```json
   "newbank": "NewBank-Checking"
   ```

4. Call the new parser from `run_import()` in `import_real_data.py`:

   ```python
   for entry in manifest.get("newbank", []):
       a, s = parse_newbank_pdf(
           store, cat, entry["path"],
           accounts.get("newbank", "NewBank-Checking"),
       )
       added += a; skipped += s
       print(f"  NewBank {entry['path']}: {a} added, {s} skipped")
   ```

5. Add fixture PDF generation to `tests/fixtures/make_pdf_fixtures.py`
   so the test suite can create a deterministic sample PDF without requiring
   a real statement.

6. Write tests in `tests/test_import_real_data.py` covering at least:
   - Normal transaction parsing (correct date, amount, merchant, account)
   - Duplicate detection (same file imported twice yields 0 added on second run)
   - Edge cases (empty PDF, malformed lines)

### Adding a New Spending Category

Categories are defined entirely in `config.json`. No code changes are
required.

1. Open `config.json` and add a new entry under `categories`:

   ```json
   "Travel": ["airbnb", "expedia", "kayak", "delta", "united", "hotel", "flight"]
   ```

   Keywords use case-insensitive substring matching against the normalized
   merchant name. Longer keywords take priority over shorter ones when
   multiple categories match the same merchant.

2. Run `finance.py summary` to verify that existing transactions are
   re-categorized when the file is re-read. Note that the category stored
   in `transactions.csv` is NOT automatically updated — the CSV stores the
   category assigned at import time. To re-categorize, the transactions must
   be re-imported or updated individually with `finance.py tag`.

3. To verify keyword coverage before re-importing, load the transactions
   DataFrame manually and apply `Categorizer.categorize()` to the merchant
   column.

### Adding a New Dashboard Tab

The dashboard UI is a 4-tab Alpine.js application. Adding a fifth tab
requires changes in two files.

1. Add a compute function in `dashboard_data.py`:

   ```python
   def compute_my_new_data(df, ...) -> list:
       # ... analytics ...
       return result
   ```

   Follow the existing pattern: accept a DataFrame and supporting dicts,
   return a serializable Python object (list of dicts, dict, etc.).

2. Call the function from `build_context()` and include the result in the
   returned dict:

   ```python
   my_new_data = compute_my_new_data(df, ...)
   return {
       ...existing keys...,
       "my_new_data": my_new_data,
   }
   ```

3. In `templates/dashboard.html.j2`, add:

   - A tab button inside the tab bar:
     ```html
     <button @click="tab='new'" :class="tab==='new' ? 'tab-active' : ''" class="tab">
       My Tab
     </button>
     ```

   - A tab panel after the existing panels:
     ```html
     <div x-show="tab==='new'">
       <!-- use {{ my_new_data }} Jinja2 variables here -->
     </div>
     ```

4. Add test coverage in `tests/test_dashboard.py` that:
   - Asserts `my_new_data` is present in the context dict returned by
     `build_context()`
   - Asserts the rendered HTML contains expected strings from the new tab

### Adding a New CLI Command

CLI commands live in `finance.py` and are decorated with Click.

1. Add a `@cli.command()` decorated function:

   ```python
   @cli.command()
   @click.option("--data-dir", default="data", hidden=True)
   def my_command(data_dir: str) -> None:
       """One-line description shown in --help."""
       store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
       df = store.load()
       # ... logic ...
       console.print("[green]Done[/green]")
   ```

2. Always include `--data-dir` with `default="data"` and `hidden=True`.
   This allows tests to pass a temporary directory without polluting the
   real data directory.

3. Use `DataStore` for all transaction access. Do not read or write
   `transactions.csv` directly.

4. Write tests in the appropriate test file (e.g.,
   `tests/test_cli_summary.py` for summary-type commands, or a new file
   `tests/test_cli_my_command.py`). Use `click.testing.CliRunner` and pass
   `--data-dir` pointing at a temporary directory populated with fixture
   data.

---

## 7. Known Limitations and Future Work

### Scale

Flat CSV works well for personal use up to approximately 10 000 transactions.
At that scale, `pandas.read_csv()` and `df.to_csv()` complete in under one
second. For a shared family or small-team use case (multiple importers
writing concurrently), consider migrating the storage layer to SQLite while
keeping the same `DataStore` interface. The interface is already abstract
enough that callers would not need to change.

### Manual Re-Categorization

Currently, changing category keyword assignments in `config.json` does not
retroactively update categories stored in `transactions.csv`. Users who want
to re-categorize existing transactions must either:

- Re-import all statements from scratch (delete `transactions.csv` first)
- Use `finance.py tag <id>` to update individual transactions

A bulk re-categorize command (`finance.py recategorize`) is a natural next
step. It would load all transactions, call `Categorizer.categorize()` on
each merchant, and write back the updated categories via `DataStore.update()`.

### Plaid Phase 2

The current import workflow requires the user to manually download PDF or CSV
statements from each bank's website. The intended next phase is to replace
manual downloads with the Plaid API, which provides programmatic access to
transaction data from thousands of financial institutions.

Implementation plan:
1. Add `importers/plaid.py` with a `PlaidImporter` class.
2. Store Plaid API keys (`PLAID_CLIENT_ID`, `PLAID_SECRET`) in a `.env`
   file at the repo root. The `.env` file must be listed in `.gitignore`
   and must never be committed.
3. Use `python-dotenv` to load keys at runtime.
4. Call `plaid_client.transactions.sync()` to fetch new transactions
   incrementally.
5. Convert Plaid's transaction format to the `DataStore` dict format
   (mapping `plaid_transaction.merchant_name`, `plaid_transaction.amount`,
   `plaid_transaction.date`, etc.).
6. Pass through `DataStore.add()` as normal; SHA256 deduplication ensures
   repeated syncs are safe.

### Multi-Currency

All amounts are stored as plain Python floats with no currency metadata.
The system assumes USD throughout. Robinhood interest is in USD, all bank
accounts are assumed to be USD, and the dashboard renders all amounts with
a `$` prefix.

Multi-currency support would require:
- Adding a `currency` column to `transactions.csv`
- Storing exchange rates (either fetched at import time or hardcoded)
- Converting amounts to a base currency for aggregation in `dashboard_data.py`
- Updating all dashboard formatting to handle non-USD symbols

### Shared Access / Concurrency

There is no file locking or concurrency protection on `transactions.csv`.
`DataStore.add()` reads the entire file, appends one row, and writes the
entire file back in a non-atomic sequence. If two processes call `add()`
simultaneously, one write will overwrite the other.

This is intentional: the system is designed for single-user local use only.
If concurrent access is required (e.g., running `import_real_data.py` while
the dashboard is being generated), use SQLite's built-in write locking
instead of the flat CSV.

---

## 8. File and Directory Layout

```
finance-tracker/
├── config.json                  Category keywords, bank formats, account names
├── finance.py                   CLI entry point (Click)
├── data_store.py                Transaction storage (CSV + SHA256)
├── categorizer.py               Keyword-based merchant categorization
├── goals.py                     goals.json read/write
├── dashboard.py                 Jinja2 rendering orchestrator
├── dashboard_data.py            All analytics (build_context + compute_*)
├── import_real_data.py          Real bank statement parsers
├── statements_manifest.json     Gitignored; real statement file paths
├── statements_manifest.example.json  Template for the manifest
├── importers/
│   ├── __init__.py
│   ├── csv_parser.py            Generic CSV importer (config-driven)
│   └── pdf_parser.py            Generic PDF importer (table-based)
├── templates/
│   ├── dashboard.html.j2        4-tab DaisyUI + Alpine.js template
│   ├── chart.min.js             Chart.js (inlined into HTML)
│   ├── daisyui.min.css          DaisyUI CSS (inlined into HTML)
│   └── alpine.min.js            Alpine.js (inlined into HTML)
├── data/
│   ├── transactions.csv         Append-only transaction ledger
│   ├── accounts.json            Account balances and types
│   └── goals.json               Monthly target, named goals, streak
├── reports/
│   └── dashboard.html           Generated dashboard (gitignored)
├── tests/
│   ├── fixtures/
│   │   ├── make_pdf_fixtures.py Generates synthetic PDF fixtures
│   │   └── *.csv, *.pdf        Sample import files for tests
│   ├── test_data_store.py
│   ├── test_categorizer.py
│   ├── test_goals.py
│   ├── test_csv_parser.py
│   ├── test_pdf_parser.py
│   ├── test_cli_import.py
│   ├── test_cli_summary.py
│   ├── test_dashboard.py
│   ├── test_dashboard_data.py
│   └── test_import_real_data.py
├── scripts/
│   ├── check_secrets.py         Pre-commit secret scanner
│   └── check_changelog.py       Enforces CHANGELOG entry on each commit
└── docs/
    └── ARCHITECTURE.md          This document
```

---

## 9. Dependency Summary

| Package | Used by | Purpose |
|---|---|---|
| `pandas` | `data_store.py`, `dashboard_data.py`, `importers/csv_parser.py`, `finance.py` | DataFrame operations, CSV I/O |
| `click` | `finance.py` | CLI argument parsing and command groups |
| `rich` | `finance.py` | Colored terminal tables and output |
| `jinja2` | `dashboard.py` | HTML template rendering |
| `pdfplumber` | `importers/pdf_parser.py`, `import_real_data.py` | PDF text and table extraction |
| `hashlib` | `data_store.py` | SHA256 ID generation (stdlib) |
| `json` | Multiple modules | JSON file read/write (stdlib) |
| `re` | `categorizer.py`, `import_real_data.py`, `importers/pdf_parser.py` | Regex merchant normalization and PDF parsing (stdlib) |

All runtime dependencies are listed in `requirements.txt`. There are no
optional dependencies — the system either works fully or not at all.
