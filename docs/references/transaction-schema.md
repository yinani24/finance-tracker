# Transaction Schema Reference

Every transaction stored in `data/transactions.csv` conforms to this schema. This document is the authoritative reference for every field.

---

## Field Reference

### `id` — Deduplication ID

| Property | Value |
|----------|-------|
| Type | `string` |
| Length | 16 hex characters |
| Example | `a3f9c2b1d4e5f601` |
| Required | Yes |

**How it is generated:**

```python
import hashlib
raw = f"{date}{amount}{merchant.lower().strip()}{account.lower().strip()}"
id = hashlib.sha256(raw.encode()).hexdigest()[:16]
```

The ID is a deterministic hash of the four most meaningful fields. Re-importing the same statement produces the same IDs, so duplicates are detected and skipped automatically.

**Implications:**
- Two transactions on the same date, with the same amount, merchant (case-insensitive), and account will produce the same ID — only the first is stored
- The ID does not include `source`, `is_income`, `is_savings`, or `notes` — editing these fields on an existing transaction does not cause a duplicate
- The ID is stable across re-imports: safe to use as a stable reference in external tools

---

### `date` — Transaction Date

| Property | Value |
|----------|-------|
| Type | `string` |
| Format | `YYYY-MM-DD` (ISO 8601) |
| Example | `2026-01-15` |
| Required | Yes |

**Notes:**
- Chase PDF statements only include MM/DD in transaction lines; the year is inferred from the statement closing date using `infer_year()`
- BofA checking statements include MM/DD/YY; the year is parsed from the 2-digit year
- All dates are stored in YYYY-MM-DD format regardless of source format

**Edge cases:**
- January transactions on a December closing statement will be assigned the prior year (handled by `infer_year`)
- BofA 2-digit years: `26` → `2026`, `99` → `1999` (Python `datetime.strptime` with `%y`)

---

### `amount` — Transaction Amount

| Property | Value |
|----------|-------|
| Type | `float` |
| Sign | **Negative = expense, Positive = income** |
| Example | `-45.20` (expense), `2500.00` (income) |
| Required | Yes |

**Sign convention:**
This is the most important field to understand. The convention is:
- **Negative amounts** represent money leaving your account (purchases, fees, transfers out)
- **Positive amounts** represent money arriving in your account (payroll, interest, refunds, transfers in)

**Per-bank sign handling:**

| Bank | Raw format | Handling |
|------|-----------|---------|
| Chase credit CSV | Negative = expense | Used as-is |
| Chase credit PDF | Positive dollar value in purchase section | Negated: `amount = -abs(value)` |
| BofA Visa CSV | Negative = expense | Used as-is |
| BofA Visa PDF | Positive value in purchase section | Negated |
| BofA checking PDF | Signed as printed on statement | Used as-is (income positive, expense negative) |
| Amex CSV | **Positive = expense** (inverted convention) | Negated: `amount_sign: "inverted"` in config |
| Robinhood CSV | Positive = income (interest, dividends) | Used as-is |

**Zero amounts:**
Transactions with `amount = 0.0` can exist (some banks include informational rows). They are stored normally but excluded from most analytics calculations.

---

### `merchant` — Merchant Name

| Property | Value |
|----------|-------|
| Type | `string` |
| Normalization | Lowercase, branch numbers removed, asterisks replaced with spaces |
| Example | `chipotle`, `amazon prime`, `netflix` |
| Required | Yes |

**Normalization rules (applied by `normalize_merchant()`):**
1. Convert to lowercase
2. Remove branch numbers: `#1234` → (removed)
3. Replace asterisks with spaces: `AMAZON*PRIME` → `amazon prime`
4. Collapse multiple spaces to one
5. Strip leading/trailing whitespace

**Examples:**
| Raw (from bank) | Stored |
|----------------|--------|
| `CHIPOTLE #1234` | `chipotle` |
| `AMAZON*PRIME` | `amazon prime` |
| `NETFLIX.COM` | `netflix.com` |
| `WHOLE FOODS MARKET #987` | `whole foods market` |
| `DOORDASH*CHIPOTLE` | `doordash chipotle` |

**Why normalize:**
Normalization ensures that the same merchant from different branches or billing formats produces the same deduplication ID.

---

### `category` — Spending Category

| Property | Value |
|----------|-------|
| Type | `string` |
| Values | One of the categories defined in `config.json → categories` |
| Default | `"Other"` (fallback when no keyword matches) |
| Example | `Food & Dining`, `Transport`, `Subscriptions` |
| Required | Yes |

**Standard categories (from default config.json):**

| Category | Example keywords |
|----------|----------------|
| `Food & Dining` | chipotle, doordash, starbucks, restaurant |
| `Transport` | uber, lyft, shell, parking |
| `Subscriptions` | netflix, spotify, apple, openai |
| `Shopping` | amazon, target, walmart, costco |
| `Health` | cvs, walgreens, doctor, gym |
| `Income` | payroll, direct deposit, salary |
| `Investments` | robinhood, fidelity, vanguard |
| `Other` | Fallback — anything that doesn't match |

**Longest-match-wins:**
If a merchant matches multiple keywords, the longest keyword wins. Example: `"whole foods"` matches both `"whole"` (if present) and `"whole foods"` — the longer match `"whole foods"` wins and determines the category.

---

### `account` — Account Name

| Property | Value |
|----------|-------|
| Type | `string` |
| Values | As configured in `config.json → import_accounts` |
| Example | `Chase-CreditCard`, `BofA-Visa`, `BofA-1234` |
| Required | Yes |

**Config-driven names:**
For CSV/PDF imports via `import_real_data.py`, account names come from `config.json → import_accounts`. This ensures no card numbers or account identifiers appear in source code.

**BofA Checking exception:**
The `parse_bofa_checking_pdf` parser derives the account name from the PDF's `Account number:` line (last 4 digits → `BofA-XXXX`). This is the only parser that does not accept an explicit account name argument.

**Manual entries:**
When using `finance.py add`, the `--account` option accepts any string. Use consistent naming across entries from the same account.

---

### `source` — Import Source

| Property | Value |
|----------|-------|
| Type | `string` |
| Values | `csv`, `pdf`, `manual` |
| Example | `pdf` |
| Required | Yes |

| Value | When set |
|-------|---------|
| `csv` | Imported via `finance.py import csv` or `parse_robinhood_csv` |
| `pdf` | Imported via `finance.py import pdf` or any PDF parser in `import_real_data.py` |
| `manual` | Added via `finance.py add` |

---

### `is_income` — Income Flag

| Property | Value |
|----------|-------|
| Type | `bool` |
| Default | `False` |
| Example | `True` for payroll deposits |
| Required | Yes |

**When True:**
- The transaction represents money arriving in the account
- Included in income calculations in `compute_kpis()`
- Excluded from expense/spending analytics

**Auto-detection in import_real_data.py:**
The BofA checking parser detects income transactions by matching keywords: `CENTAVO`, `PAYROLL`, `BKOFAMERICA.*DEPOSIT`, `Zelle payment from`.

**Manual tagging:**
```bash
python finance.py tag <transaction_id> --income
```

---

### `is_savings` — Savings Transfer Flag

| Property | Value |
|----------|-------|
| Type | `bool` |
| Default | `False` |
| Example | `True` for Robinhood transfers |
| Required | Yes |

**When True:**
- The transaction represents a transfer to a savings/investment account
- Counted toward the monthly savings rate calculation
- Excluded from regular expense analytics

**Auto-detection:**
The BofA checking parser marks transactions matching `ROBINHOOD` as savings transfers.

**Manual tagging:**
```bash
python finance.py tag <transaction_id> --savings
```

---

### `notes` — Free-Text Annotation

| Property | Value |
|----------|-------|
| Type | `string` |
| Default | `""` (empty string) |
| Example | `"Robinhood interest"`, `"Business expense"` |
| Required | Yes (can be empty) |

**When populated automatically:**
- Robinhood CSV rows: `"Robinhood interest"`
- Robinhood PDF interest rows: `"Robinhood interest"`
- Robinhood PDF Gold subscription rows: `"Robinhood Gold fee"`
- Robinhood PDF dividend rows: `"Robinhood dividend"`
- Robinhood PDF crypto transfers: `"Crypto money movement"`

---

## Full Column Order

The CSV is written with columns in this order:

```
id,date,amount,merchant,category,account,source,is_income,is_savings,notes
```

---

## Deduplication Behavior

When `DataStore.add(tx)` is called:
1. `is_duplicate(tx)` checks whether `tx["id"]` exists in the loaded DataFrame
2. If it exists: the transaction is **skipped** (not added, not updated)
3. If it does not exist: the transaction is **appended** to the CSV

**Consequence:** Once a transaction is stored, its `amount`, `merchant`, `category`, and `account` cannot be changed by re-importing. Only `notes`, `is_income`, `is_savings`, and `category` can be updated via `DataStore.update()` or `finance.py tag`.

---

## Schema Evolution Policy

The schema is currently flat and has not changed since v0.1.0. If a new field is added in a future version:
- Old CSV files without the new column will load with `NaN` for that column
- `DataStore.load()` returns a DataFrame; consumers handle missing columns gracefully
- A migration script will be provided for breaking changes

---

## Example Rows

```csv
id,date,amount,merchant,category,account,source,is_income,is_savings,notes
a3f9c2b1d4e5f601,2026-01-15,-45.20,chipotle,Food & Dining,Chase-CreditCard,pdf,False,False,
b7d2e4c8f1a6b302,2026-01-17,2500.00,payroll,Income,BofA-1234,pdf,True,False,
c1e5f7a9b3d4c503,2026-01-18,-500.00,robinhood,Investments,BofA-1234,pdf,False,True,
d9f3a1b5c7e8d604,2026-01-20,1.50,robinhood interest,Investments,Robinhood,csv,True,False,Robinhood interest
```
