# Bank Formats Reference

This document describes every supported bank format, the two importer paths (CSV and PDF), how merchant names and amounts are normalised, and how to add a new bank.

---

## Two Import Paths

### Path 1 — Generic importers (`finance.py import csv / import pdf`)

Uses `importers/csv_parser.py` and `importers/pdf_parser.py`. These are driven entirely by `config.json → bank_formats`. They work for any bank whose CSV exports have consistent column headers, or whose PDF exports use simple tables detectable by `pdfplumber.extract_table()`.

```bash
python finance.py import csv ~/Downloads/Chase_Activity.csv \
  --account Chase-CreditCard --bank chase

python finance.py import pdf ~/Downloads/Amex_Statement.pdf \
  --account Amex-Credit --bank amex
```

### Path 2 — Real statement importers (`import_real_data.py`)

Uses bank-specific regex and layout parsers in `import_real_data.py`. These handle the real-world statement formats from Chase, BofA, and Robinhood, which use text-layout PDFs that `pdfplumber.extract_table()` cannot reliably parse.

```bash
python3 import_real_data.py
```

This script reads file paths from `statements_manifest.json` (gitignored) and account names from `config.json → import_accounts`.

---

## Supported Banks

### Chase Credit Card

#### CSV Format (`--bank chase`)

| Config key | Value |
|-----------|-------|
| `date_col` | `"Transaction Date"` |
| `amount_col` | `"Amount"` |
| `merchant_col` | `"Description"` |
| `amount_sign` | `"standard"` (negative = expense) |

**Typical CSV header row:**

```
Transaction Date,Post Date,Description,Category,Type,Amount,Memo
```

**Date format:** `MM/DD/YYYY` — parsed by `pandas.to_datetime()`.

**Example row:**

```
01/15/2026,01/17/2026,CHIPOTLE #1234,,Sale,-45.20,
```

#### PDF Format (`import_real_data.py`)

The real Chase credit card PDF uses text-layout statements, not tables. `parse_chase_credit_pdf()` uses the following logic:

- Opens the PDF with `pdfplumber`, reads text page by page
- Detects the statement closing date from a line matching `Opening/Closing Date ... MM/DD/YYYY` to infer the year for transactions
- Matches purchase lines with regex: `(\d{2}/\d{2})\s+(.+?)\s+([\d,]+\.\d{2})`
- Date format is `MM/DD` (no year); year is inferred using `infer_year()` which handles January transactions appearing on December statements
- Amount is always stored as negative (all matched lines are charges)
- Account name comes from `config.json → import_accounts["chase_credit"]`
- Statement file path comes from `statements_manifest.json["chase_credit"]`

**Manifest keys:**

```json
{
  "chase_credit": {
    "path": "/path/to/Chase_Statement.pdf",
    "closing_year": 2026,
    "closing_month": 1
  }
}
```

`closing_year` and `closing_month` are required for year inference.

---

### Bank of America (BofA) Visa Credit Card

#### CSV Format (`--bank bofa`)

| Config key | Value |
|-----------|-------|
| `date_col` | `"Date"` |
| `amount_col` | `"Amount"` |
| `merchant_col` | `"Description"` |
| `amount_sign` | `"standard"` (negative = expense) |

**Typical CSV header row:**

```
Date,Description,Amount,Running Bal.
```

**Date format:** `MM/DD/YYYY`.

#### PDF Format (`import_real_data.py`)

`parse_bofa_visa_pdf()` handles BofA Visa credit card statements:

- Reads text with `pdfplumber` page by page
- Matches lines with regex: `(\d{2}/\d{2}/\d{2})\s+(.+?)\s+([\d,]+\.\d{2})`
- Date format is `MM/DD/YY` — the 2-digit year is parsed with `datetime.strptime(..., "%m/%d/%y")`
- Amount is stored as negative (all matched lines are charges)
- Account name comes from `config.json → import_accounts["bofa_visa"]`

**Manifest keys:**

```json
{
  "bofa_visa": {
    "path": "/path/to/BofA_Visa_Statement.pdf",
    "year": 2026
  }
}
```

`year` is used as a sanity check but the 2-digit year in the PDF is the primary source of truth.

---

### Bank of America (BofA) Checking / Savings

#### PDF Format only (`import_real_data.py`)

BofA checking statements are only available as PDFs via `import_real_data.py`. There is no CSV option because the bank's CSV export format for checking accounts is not supported.

`parse_bofa_checking_pdf()` logic:

- Reads text with `pdfplumber` page by page
- Extracts the account number from a line matching `Account number: XXXX XXXX XXXX XXXX` and uses the last 4 digits to form the account name: `BofA-XXXX`
- **This is the only parser that does not accept an explicit account name.** The account name is derived from the PDF itself.
- Matches transaction lines with regex: `(\d{2}/\d{2}/\d{2})\s+(.+?)\s+(-?[\d,]+\.\d{2})`
- Amounts are used as-is (the statement already uses the correct sign convention)
- Income detection: lines matching `CENTAVO`, `PAYROLL`, `BKOFAMERICA.*DEPOSIT`, or `Zelle payment from` are tagged `is_income=True`
- Savings detection: lines matching `ROBINHOOD` are tagged `is_savings=True`

**Manifest keys:**

```json
{
  "bofa_checking": {
    "path": "/path/to/BofA_Checking_Statement.pdf"
  }
}
```

No `year` key is needed — dates include 2-digit years directly.

---

### American Express (Amex)

#### CSV Format (`--bank amex`)

| Config key | Value |
|-----------|-------|
| `date_col` | `"Date"` |
| `amount_col` | `"Amount"` |
| `merchant_col` | `"Description"` |
| `amount_sign` | `"inverted"` (positive = expense) |

**Typical CSV header row:**

```
Date,Description,Amount,Extended Details,...
```

**Sign convention:** Amex exports charges as **positive numbers**. The `amount_sign: "inverted"` config key causes `CSVParser` to negate every amount: `amount = -raw_amount`.

**Date format:** `MM/DD/YYYY`.

#### PDF Format (`importers/pdf_parser.py`)

The generic `PDFParser` uses `_parse_regex()` for `--bank amex`:

- Matches lines with regex: `(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([\d,]+\.\d{2})`
- Amount is always negated at parse time (same inverted convention as CSV)

There is no real-statement Amex parser in `import_real_data.py`. Use `finance.py import pdf` for Amex PDFs.

---

### Robinhood

#### CSV Format (`import_real_data.py`)

`parse_robinhood_csv()` handles Robinhood brokerage activity exports:

- Reads the CSV with the `csv` module (not pandas) for safety
- Expected columns: `Date`, `Trans. Type`, `Description`, `Amount`
- `Date` format: `MM/DD/YYYY`
- Amount field may contain `$` signs and commas — stripped before conversion
- All transactions are tagged `is_income=True` and `source="csv"` (Robinhood CSV represents dividends, interest, and deposits — all income)
- Notes are populated based on description patterns:
  - "interest" in description → `"Robinhood interest"`
  - other descriptions → `"Robinhood activity"`
- Account name comes from `config.json → import_accounts["robinhood"]`

**Manifest keys:**

```json
{
  "robinhood": {
    "path": "/path/to/Robinhood_Activity.csv"
  }
}
```

#### PDF Format (`import_real_data.py`)

`parse_robinhood_pdf()` handles Robinhood brokerage PDF statements:

- Reads text with `pdfplumber`
- Matches interest lines with regex: `(\w+ \d{1,2}, \d{4})\s+Interest\s+([\d.]+)`
- Matches Gold fee lines with regex: `(\w+ \d{1,2}, \d{4})\s+Robinhood Gold\s+([\d.]+)`
- Matches dividend lines with regex: `(\w+ \d{1,2}, \d{4})\s+Dividend\s+([\d.]+)`
- Matches crypto transfer lines with regex: `(\w+ \d{1,2}, \d{4})\s+Money Movement\s+([\d.]+)`
- Date format: `"Month DD, YYYY"` (e.g. `"January 15, 2026"`) — parsed with `strptime(..., "%B %d, %Y")`
- Interest and dividends: `is_income=True`; Gold fees: `is_income=False` (expense)
- Notes field is populated per line type (e.g. `"Robinhood interest"`, `"Robinhood Gold fee"`)
- Account name comes from `config.json → import_accounts["robinhood"]`

**Manifest keys:**

```json
{
  "robinhood_pdf": {
    "path": "/path/to/Robinhood_Statement.pdf"
  }
}
```

---

## Merchant Normalisation

All importers apply `normalize_merchant()` before storing the merchant name:

```python
def normalize_merchant(name: str) -> str:
    name = name.lower()
    name = re.sub(r'#\d+', '', name)   # remove branch numbers
    name = re.sub(r'\*', ' ', name)    # asterisks → spaces
    name = re.sub(r'\s+', ' ', name)   # collapse whitespace
    return name.strip()
```

| Raw (from bank) | Stored |
|----------------|--------|
| `CHIPOTLE #1234` | `chipotle` |
| `AMAZON*PRIME` | `amazon prime` |
| `NETFLIX.COM` | `netflix.com` |
| `WHOLE FOODS MARKET #987` | `whole foods market` |

Normalisation ensures consistent deduplication IDs across re-imports.

---

## Amount Sign Conventions

| Bank / Parser | Raw format | Stored convention |
|--------------|-----------|-------------------|
| Chase CSV | Negative = expense | Used as-is |
| Chase PDF (real) | Positive dollar values in charge section | Negated: `-abs(value)` |
| BofA Visa CSV | Negative = expense | Used as-is |
| BofA Visa PDF (real) | Positive values in charge section | Negated |
| BofA Checking PDF (real) | Signed as printed | Used as-is |
| Amex CSV | **Positive = expense** | Negated via `amount_sign: "inverted"` |
| Amex PDF (generic) | Positive = expense | Negated in `_parse_regex()` |
| Robinhood CSV | Positive = income | Used as-is |
| Robinhood PDF | Positive = income/fee | Income is positive; Gold fee is negated |

The stored convention is always: **negative = expense, positive = income**.

---

## Statements Manifest

`statements_manifest.json` is **gitignored** and must be created locally. It maps bank keys to statement file paths and optional metadata. See `statements_manifest.example.json` for the full template:

```json
{
  "chase_credit": {
    "path": "/path/to/statement.pdf",
    "closing_year": 2026,
    "closing_month": 1
  },
  "bofa_visa": {
    "path": "/path/to/statement.pdf",
    "year": 2026
  },
  "bofa_checking": {
    "path": "/path/to/statement.pdf"
  },
  "robinhood": {
    "path": "/path/to/activity.csv"
  },
  "robinhood_pdf": {
    "path": "/path/to/statement.pdf"
  }
}
```

You can omit any bank key you don't use — `import_real_data.py` skips missing keys silently.

---

## Adding a New Bank

### For CSV imports (generic path)

1. Add a new key to `config.json → bank_formats`:

```json
"newbank": {
  "date_col": "Transaction Date",
  "amount_col": "Debit Amount",
  "merchant_col": "Merchant Name",
  "amount_sign": "standard"
}
```

2. Add the bank key to `--bank`'s allowed choices in `finance.py`:

```python
@click.option("--bank", required=True,
              type=click.Choice(["chase", "bofa", "amex", "newbank"]))
```

3. Test: `python finance.py import csv file.csv --bank newbank --account MyAccount`

### For real-statement imports (`import_real_data.py`)

1. Write a `parse_newbank_pdf()` function in `import_real_data.py` following the existing pattern: open with `pdfplumber`, match lines with regex, call `_add_tx()` for each match.

2. Add an account key to `config.json → import_accounts`:

```json
"newbank_credit": "NewBank-Credit"
```

3. Add a manifest key to `statements_manifest.json`:

```json
"newbank": {
  "path": "/path/to/statement.pdf"
}
```

4. Call `parse_newbank_pdf()` in `run_import()` in `import_real_data.py`.

5. Add fixture PDF to `tests/fixtures/` and add tests in `tests/test_import_real_data.py`.

See [docs/CONTRIBUTING.md](../CONTRIBUTING.md) for the full contribution guide.
