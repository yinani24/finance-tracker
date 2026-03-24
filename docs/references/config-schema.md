# Config Schema Reference

All configuration for the finance-tracker lives in `config.json` at the repo root. This document describes every key, its type, default, and how it is used.

---

## Top-Level Structure

```json
{
  "bank_formats": { ... },
  "import_accounts": { ... },
  "categories": { ... }
}
```

---

## `bank_formats`

Controls how `importers/csv_parser.py` maps CSV columns to the transaction schema. Each key is a bank identifier passed to `--bank` on the CLI.

### Structure

```json
"bank_formats": {
  "<bank_key>": {
    "date_col": "<column header for date>",
    "amount_col": "<column header for amount>",
    "merchant_col": "<column header for merchant/description>",
    "amount_sign": "standard" | "inverted"
  }
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `date_col` | string | Yes | Exact column header for the transaction date |
| `amount_col` | string | Yes | Exact column header for the amount |
| `merchant_col` | string | Yes | Exact column header for the merchant/description |
| `amount_sign` | string | Yes | `"standard"` (negative = expense) or `"inverted"` (positive = expense, as in Amex) |

### Current Bank Formats

#### `chase`

```json
"chase": {
  "date_col": "Transaction Date",
  "amount_col": "Amount",
  "merchant_col": "Description",
  "amount_sign": "standard"
}
```

- **Date format:** `MM/DD/YYYY`
- **Sign:** Negative = expense
- **Typical CSV header row:** `Transaction Date,Post Date,Description,Category,Type,Amount,Memo`

#### `bofa`

```json
"bofa": {
  "date_col": "Date",
  "amount_col": "Amount",
  "merchant_col": "Description",
  "amount_sign": "standard"
}
```

- **Date format:** `MM/DD/YYYY`
- **Sign:** Negative = expense
- **Typical CSV header row:** `Date,Description,Amount,Running Bal.`

#### `amex`

```json
"amex": {
  "date_col": "Date",
  "amount_col": "Amount",
  "merchant_col": "Description",
  "amount_sign": "inverted"
}
```

- **Date format:** `MM/DD/YYYY`
- **Sign:** **Positive = expense** (inverted). Amex exports charges as positive numbers; the parser negates them.
- **Typical CSV header row:** `Date,Description,Amount,Extended Details,...`

### Adding a New Bank Format

To add support for a new bank CSV format, add a new key under `bank_formats`:

```json
"newbank": {
  "date_col": "Transaction Date",
  "amount_col": "Debit Amount",
  "merchant_col": "Merchant Name",
  "amount_sign": "standard"
}
```

Then test: `python finance.py import csv file.csv --bank newbank --account MyAccount`

See [docs/CONTRIBUTING.md](../CONTRIBUTING.md) for the full guide.

---

## `import_accounts`

Maps logical account keys to human-readable account name strings. Used by `import_real_data.py` to tag transactions without hardcoding card numbers or account identifiers in source code.

### Structure

```json
"import_accounts": {
  "<account_key>": "<account_name_string>"
}
```

### Current Values

```json
"import_accounts": {
  "chase_credit":   "Chase-CreditCard",
  "bofa_visa":      "BofA-Visa",
  "bofa_checking":  "BofA-Checking",
  "robinhood":      "Robinhood"
}
```

### Fields

| Key | Type | Description |
|-----|------|-------------|
| `chase_credit` | string | Account name used for Chase credit card transactions |
| `bofa_visa` | string | Account name used for BofA Visa credit card transactions |
| `bofa_checking` | string | Account name used for BofA checking/savings transactions (fallback only — the PDF parser reads the last-4-digit account number from the PDF itself) |
| `robinhood` | string | Account name used for Robinhood CSV and PDF brokerage transactions |

### Adding a New Account

When adding a new bank parser to `import_real_data.py`, add a corresponding key here:

```json
"import_accounts": {
  "newbank_credit": "NewBank-Credit"
}
```

Then read it in `run_import()` via `accounts.get("newbank_credit", "NewBank-Credit")`.

### BofA Checking Special Case

The `parse_bofa_checking_pdf` parser derives the account name from the PDF's `Account number:` field (last 4 digits → `BofA-XXXX`). The `bofa_checking` key in `import_accounts` is used as a fallback only and is not typically applied.

---

## `categories`

Defines spending categories and their keyword lists. Used by `Categorizer.categorize()` to assign a category to every imported transaction.

### Structure

```json
"categories": {
  "<category_name>": ["<keyword1>", "<keyword2>", ...]
}
```

### Matching Algorithm

1. The merchant name is normalized (lowercase, branch numbers removed, asterisks → spaces)
2. Every keyword in every category is checked as a **substring** of the normalized merchant
3. **Longest match wins:** if multiple keywords from different categories match, the longest keyword determines the category
4. If no keyword matches: the transaction is assigned to `"Other"`
5. `"Other"` has an empty keyword list `[]` and is the fallback

### Current Categories

#### `Food & Dining`

```json
"Food & Dining": ["chipotle", "mcdonald", "doordash", "uber eats", "grubhub",
                   "starbucks", "restaurant", "pizza", "sushi", "cafe", "diner"]
```

#### `Transport`

```json
"Transport": ["uber", "lyft", "shell", "exxon", "bp", "chevron",
               "parking", "metro", "transit", "toll"]
```

**Note:** `"uber"` matches both Uber rides and Uber Eats. Because `"uber eats"` is longer than `"uber"`, Uber Eats transactions are correctly categorized as `Food & Dining`, not `Transport`.

#### `Subscriptions`

```json
"Subscriptions": ["netflix", "spotify", "apple", "amazon prime", "adobe",
                   "hulu", "disney", "youtube", "openai"]
```

**Note:** `"amazon prime"` (12 chars) beats `"amazon"` (6 chars) for Amazon Prime charges. Regular Amazon shopping still matches the shorter `"amazon"` keyword in `Shopping`.

#### `Shopping`

```json
"Shopping": ["amazon", "target", "walmart", "costco", "best buy", "gap", "zara", "h&m"]
```

#### `Health`

```json
"Health": ["cvs", "walgreens", "rite aid", "urgent care", "doctor",
            "dentist", "gym", "planet fitness"]
```

#### `Income`

```json
"Income": ["payroll", "direct deposit", "salary", "zelle from", "venmo from"]
```

#### `Investments`

```json
"Investments": ["robinhood", "fidelity", "vanguard", "schwab"]
```

#### `Other`

```json
"Other": []
```

Fallback category. Empty keyword list — nothing matches here directly. Always the last resort.

### Adding a New Category

```json
"categories": {
  "Healthcare": ["pharmacy", "cvs", "walgreens", "doctor", "hospital", "dental"],
  ...
}
```

**Important:** Add the new category **before** `"Other"` in the JSON object to ensure it is evaluated. (Python dicts preserve insertion order in 3.7+.)

### Keyword Conflict Resolution Examples

| Merchant | Matching keywords | Winner | Category |
|----------|------------------|--------|----------|
| `amazon prime` | `"amazon"` (Shopping), `"amazon prime"` (Subscriptions) | `"amazon prime"` (longer) | Subscriptions |
| `uber eats` | `"uber"` (Transport), `"uber eats"` (Food & Dining) | `"uber eats"` (longer) | Food & Dining |
| `planet fitness` | `"gym"` (Health), `"planet fitness"` (Health) | `"planet fitness"` (longer) | Health |
| `unknown merchant xyz` | none | — | Other |
