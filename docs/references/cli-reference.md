# CLI Reference

All commands are invoked as `python finance.py <command> [options]`. Run `python finance.py --help` for a summary or `python finance.py <command> --help` for per-command help.

---

## `import csv`

Import transactions from a CSV bank export.

```bash
python finance.py import csv <filepath> --account <name> --bank <bank>
```

### Options

| Option | Required | Values | Description |
|--------|----------|--------|-------------|
| `filepath` | Yes | path | Path to the CSV file |
| `--account` | Yes | string | Account name to tag transactions with (e.g. `Chase-CreditCard`) |
| `--bank` | Yes | `chase`, `bofa`, `amex` | Bank format profile from config.json |
| `--data-dir` | No | path (default: `data`) | Data directory |

### Examples

```bash
# Chase credit card
python finance.py import csv ~/Downloads/Chase_Activity.csv \
  --account Chase-CreditCard --bank chase

# Bank of America checking
python finance.py import csv ~/Downloads/BoA_Activity.csv \
  --account BofA-Checking --bank bofa

# Amex (sign is inverted automatically)
python finance.py import csv ~/Downloads/Amex_Activity.csv \
  --account Amex-Credit --bank amex
```

### Output

```
✓ Imported 47 new transactions (3 skipped as duplicates)
```

### Error Cases

- **File not found:** `Error: Could not open file 'path': No such file or directory`
- **Invalid bank:** `Error: Invalid value for '--bank': 'wellsfargo' is not one of 'chase', 'bofa', 'amex'`
- **Missing column:** KeyError if the CSV does not have the expected column header for the bank format

---

## `import pdf`

Import transactions from a PDF bank statement using the generic table-based parser.

```bash
python finance.py import pdf <filepath> --account <name> --bank <bank>
```

### Options

Same as `import csv`.

### Notes

The generic PDF parser (`importers/pdf_parser.py`) uses `pdfplumber.extract_table()` and works for simple table-format PDFs. For real Chase, BofA, and Robinhood statements (which use text-layout formats), use `python3 import_real_data.py` instead.

### Output

```
✓ Imported 12 new transactions (0 skipped as duplicates)
```

---

## `add`

Manually add a single transaction.

```bash
python finance.py add --amount <n> --merchant <name> --account <name> [options]
```

### Options

| Option | Required | Type | Description |
|--------|----------|------|-------------|
| `--amount` | Yes | float | Transaction amount (negative = expense, positive = income) |
| `--merchant` | Yes | string | Merchant name |
| `--account` | Yes | string | Account name |
| `--category` | No | string | Override auto-categorization |
| `--income` | No | flag | Mark as income |
| `--savings` | No | flag | Mark as savings transfer |
| `--date` | No | YYYY-MM-DD (default: today) | Transaction date |
| `--data-dir` | No | path (default: `data`) | Data directory |

### Examples

```bash
# Add an expense
python finance.py add --amount -45.20 --merchant "Chipotle" --account Chase-CreditCard

# Add income
python finance.py add --amount 2500.00 --merchant "Payroll" --account BofA-Checking --income

# Add a savings transfer
python finance.py add --amount -500.00 --merchant "Robinhood" --account BofA-Checking --savings

# Override category
python finance.py add --amount -120.00 --merchant "Office Depot" --account Chase \
  --category "Business"
```

### Output

```
✓ Transaction added: 2026-01-15 | chipotle | -45.20 | Food & Dining | Chase-CreditCard
```

---

## `summary`

Show income and expense summary for a month.

```bash
python finance.py summary [--month YYYY-MM]
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--month` | No | current month | Month to summarize as YYYY-MM |
| `--data-dir` | No | `data` | Data directory |

### Examples

```bash
# Current month
python finance.py summary

# Specific month
python finance.py summary --month 2026-01
```

### Output

```
Summary for 2026-01

Income:    $5,000.00
Expenses: -$2,847.32
Savings:    $500.00
Net:        $2,152.68

Top categories:
  Food & Dining:   $487.20
  Subscriptions:   $89.97
  Transport:       $156.40
```

---

## `top-categories`

Show top spending categories over a trailing period.

```bash
python finance.py top-categories [--last N]
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--last` | No | `3months` | Number of months to look back (integer or `Nmonths`) |
| `--data-dir` | No | `data` | Data directory |

### Examples

```bash
python finance.py top-categories
python finance.py top-categories --last 6
```

### Output

```
Top categories (last 3 months)

  Food & Dining      $1,245.60   ████████████
  Transport            $487.20   █████
  Subscriptions        $269.91   ███
  Shopping             $234.50   ██
```

---

## `spending`

Show month-by-month spending trend for a specific category.

```bash
python finance.py spending --category <name> [--year YYYY]
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--category` | Yes | — | Category name (must match config.json) |
| `--year` | No | current year | Year to show |
| `--data-dir` | No | `data` | Data directory |

### Examples

```bash
python finance.py spending --category "Food & Dining"
python finance.py spending --category "Subscriptions" --year 2025
```

### Output

```
Food & Dining — 2026

Jan  $487.20  ████████████
Feb  $412.50  ██████████
Mar  $530.80  █████████████
...
```

---

## `networth`

Calculate net worth from account balances stored in `data/accounts.json`.

```bash
python finance.py networth
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--data-dir` | No | `data` | Data directory |

### Output

```
Net Worth

  Chase-CreditCard    -$1,234.56   (credit)
  BofA-Checking        $4,200.00   (checking)
  Robinhood           $12,500.00   (investment)
  ─────────────────────────────
  Total               $15,465.44
```

---

## `account update`

Update an account's balance and/or type in `data/accounts.json`.

```bash
python finance.py account update <name> --balance <amount> [--type <type>]
```

### Options

| Option | Required | Values | Description |
|--------|----------|--------|-------------|
| `name` | Yes | string | Account name |
| `--balance` | Yes | float | Current balance |
| `--type` | No | `checking`, `savings`, `credit`, `investment` | Account type |
| `--data-dir` | No | `data` | Data directory |

### Examples

```bash
python finance.py account update "BofA-Checking" --balance 4200.00 --type checking
python finance.py account update "Robinhood" --balance 13500.00 --type investment
python finance.py account update "Chase-CreditCard" --balance -987.43 --type credit
```

### Output

```
✓ Account updated: BofA-Checking | $4,200.00 | checking
```

---

## `tag`

Tag an existing transaction as income or savings.

```bash
python finance.py tag <transaction_id> [--income] [--savings]
```

### Options

| Option | Required | Description |
|--------|----------|-------------|
| `transaction_id` | Yes | The 16-char hex transaction ID |
| `--income` | No | Mark as income |
| `--savings` | No | Mark as savings transfer |
| `--data-dir` | No | Data directory |

### Examples

```bash
python finance.py tag a3f9c2b1d4e5f601 --income
python finance.py tag b7d2e4c8f1a6b302 --savings
```

### Finding a transaction ID

```bash
# Show recent transactions to find the ID
python finance.py summary
```

Transaction IDs appear in summary output as 16-character hex strings.

### Output

```
✓ Tagged a3f9c2b1d4e5f601 as income
```

### Error Cases

- **ID not found:** `Error: Transaction a3f9c2b1d4e5f601 not found`

---

## `goal set`

Set a monthly savings target or add a named savings goal.

### Set monthly target

```bash
python finance.py goal set monthly --amount <n>
```

```bash
python finance.py goal set monthly --amount 500
# ✓ Monthly savings target set: $500.00
```

### Add a named goal

```bash
python finance.py goal set <name> --target <n> --by <YYYY-MM>
```

```bash
python finance.py goal set "Emergency Fund" --target 10000 --by 2026-12
# ✓ Goal added: Emergency Fund | target $10,000.00 | deadline 2026-12
```

### Options

| Option | Required | Description |
|--------|----------|-------------|
| `name` | Yes | `monthly` for monthly target, or any string for a named goal |
| `--amount` | For monthly | Monthly target amount in dollars |
| `--target` | For named | Total target amount in dollars |
| `--by` | For named | Deadline as YYYY-MM |
| `--data-dir` | No | Data directory |

---

## `goal status`

Show progress toward all savings goals.

```bash
python finance.py goal status
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--data-dir` | No | `data` | Data directory |

### Output

```
Savings Goals

Monthly target: $500.00
  Jan 2026:  $480.00  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░  96%
  Dec 2025:  $520.00  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  100% ✓

Named goals:
  Emergency Fund     $2,400/$10,000   24%   deadline 2026-12
  Vacation Fund        $800/$3,000    27%   deadline 2026-06  ⚠ at risk
```

---

## `dashboard`

Generate the HTML dashboard and optionally open it in the browser.

```bash
python finance.py dashboard [--output <path>] [--no-open]
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--output` | No | `reports/dashboard.html` | Output path for the HTML file |
| `--no-open` | No | False (opens browser) | Generate without opening browser |
| `--data-dir` | No | `data` | Data directory |

### Examples

```bash
# Generate and open in browser (default)
python finance.py dashboard

# Generate to custom path without opening
python finance.py dashboard --output /tmp/finance_report.html --no-open
```

### Output

```
Dashboard generated: reports/dashboard.html
[opens in default browser]
```

### Error Cases

- **No transactions:** Dashboard generates successfully but shows empty state in all tabs
- **Missing accounts.json:** Net worth section shows $0.00 for all accounts
- **Missing goals.json:** Goals tab shows no goals configured
