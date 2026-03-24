# Finance Tracker Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI + HTML dashboard personal finance tracker that imports transactions from Chase/BofA/Amex PDFs and CSVs, auto-categorizes spending, tracks net worth including Robinhood, and monitors savings goals.

**Architecture:** Flat-file storage — all transactions land in a single `transactions.csv` regardless of source. A `click`-based CLI (`finance.py`) is the sole entry point. The dashboard is a fully self-contained HTML file generated on demand with Chart.js bundled inline.

**Tech Stack:** Python 3.10+, click, pandas, pdfplumber, rich, Jinja2, pytest

---

## Chunk 1: Project Scaffold & Core Data Layer

### Task 1: Project Setup

**Files:**
- Create: `finance-tracker/requirements.txt`
- Create: `finance-tracker/config.json`
- Create: `finance-tracker/.gitignore`
- Create: `finance-tracker/data/.gitkeep`
- Create: `finance-tracker/reports/.gitkeep`

- [ ] **Step 1: Create the project directory and initialize git**

```bash
mkdir -p finance-tracker/data finance-tracker/reports finance-tracker/importers finance-tracker/tests
cd finance-tracker
git init
```

- [ ] **Step 2: Create `requirements.txt`**

```
click==8.1.7
pandas==2.2.0
pdfplumber==0.11.0
rich==13.7.0
Jinja2==3.1.3
pytest==8.0.0
python-dotenv==1.0.0
```

- [ ] **Step 3: Create `config.json`**

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
  },
  "categories": {
    "Food & Dining": ["chipotle", "mcdonald", "doordash", "uber eats", "grubhub", "starbucks", "restaurant", "pizza", "sushi", "cafe", "diner"],
    "Transport": ["uber", "lyft", "shell", "exxon", "bp", "chevron", "parking", "metro", "transit", "toll"],
    "Subscriptions": ["netflix", "spotify", "apple", "amazon prime", "adobe", "hulu", "disney", "youtube", "openai"],
    "Shopping": ["amazon", "target", "walmart", "costco", "best buy", "gap", "zara", "h&m"],
    "Health": ["cvs", "walgreens", "rite aid", "urgent care", "doctor", "dentist", "gym", "planet fitness"],
    "Income": ["payroll", "direct deposit", "salary", "zelle from", "venmo from"],
    "Investments": ["robinhood", "fidelity", "vanguard", "schwab"],
    "Other": []
  }
}
```

- [ ] **Step 4: Create `.gitignore`**

```
.env
data/transactions.csv
data/accounts.json
data/goals.json
reports/
__pycache__/
*.pyc
.pytest_cache/
.superpowers/
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: All packages install without errors.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt config.json .gitignore data/.gitkeep reports/.gitkeep
git commit -m "chore: project scaffold and config"
```

---

### Task 2: Transaction Data Layer

**Files:**
- Create: `finance-tracker/data_store.py`
- Create: `finance-tracker/tests/test_data_store.py`

- [ ] **Step 1: Write failing tests for data store**

Create `tests/test_data_store.py`:

```python
import os
import pytest
import pandas as pd
from data_store import DataStore

@pytest.fixture
def tmp_store(tmp_path):
    return DataStore(transactions_path=str(tmp_path / "transactions.csv"))

def test_empty_store_returns_empty_dataframe(tmp_store):
    df = tmp_store.load()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0

def test_add_transaction_persists(tmp_store):
    tx = {
        "id": "abc123",
        "date": "2024-01-15",
        "amount": -45.20,
        "merchant": "Chipotle",
        "category": "Food & Dining",
        "account": "Chase-Checking",
        "source": "manual",
        "is_income": False,
        "is_savings": False,
        "notes": ""
    }
    tmp_store.add(tx)
    df = tmp_store.load()
    assert len(df) == 1
    assert df.iloc[0]["merchant"] == "Chipotle"

def test_duplicate_transaction_not_added(tmp_store):
    tx = {
        "id": "abc123",
        "date": "2024-01-15",
        "amount": -45.20,
        "merchant": "Chipotle",
        "category": "Food & Dining",
        "account": "Chase-Checking",
        "source": "manual",
        "is_income": False,
        "is_savings": False,
        "notes": ""
    }
    tmp_store.add(tx)
    is_dup = tmp_store.is_duplicate(tx)
    assert is_dup is True

def test_different_transaction_not_flagged_as_duplicate(tmp_store):
    tx1 = {"id": "abc123", "date": "2024-01-15", "amount": -45.20, "merchant": "Chipotle",
            "category": "Food & Dining", "account": "Chase-Checking", "source": "manual",
            "is_income": False, "is_savings": False, "notes": ""}
    tx2 = {"id": "def456", "date": "2024-01-16", "amount": -12.99, "merchant": "Netflix",
            "category": "Subscriptions", "account": "BofA-Credit", "source": "manual",
            "is_income": False, "is_savings": False, "notes": ""}
    tmp_store.add(tx1)
    assert tmp_store.is_duplicate(tx2) is False

def test_update_transaction_field(tmp_store):
    tx = {"id": "abc123", "date": "2024-01-15", "amount": -45.20, "merchant": "Chipotle",
          "category": "Food & Dining", "account": "Chase-Checking", "source": "manual",
          "is_income": False, "is_savings": False, "notes": ""}
    tmp_store.add(tx)
    tmp_store.update("abc123", {"is_income": True})
    df = tmp_store.load()
    assert df.iloc[0]["is_income"] == True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_data_store.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'data_store'`

- [ ] **Step 3: Implement `data_store.py`**

```python
import hashlib
import pandas as pd

COLUMNS = ["id", "date", "amount", "merchant", "category", "account",
           "source", "is_income", "is_savings", "notes"]

def generate_id(date: str, amount: float, merchant: str, account: str) -> str:
    raw = f"{date}{amount}{merchant.lower().strip()}{account}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

class DataStore:
    def __init__(self, transactions_path: str = "data/transactions.csv"):
        self.path = transactions_path

    def load(self) -> pd.DataFrame:
        try:
            df = pd.read_csv(self.path, dtype={"id": str})
            return df
        except FileNotFoundError:
            return pd.DataFrame(columns=COLUMNS)

    def add(self, tx: dict) -> None:
        df = self.load()
        new_row = pd.DataFrame([tx])
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(self.path, index=False)

    def is_duplicate(self, tx: dict) -> bool:
        df = self.load()
        if df.empty:
            return False
        return tx["id"] in df["id"].values

    def update(self, tx_id: str, fields: dict) -> None:
        df = self.load()
        for key, value in fields.items():
            df.loc[df["id"] == tx_id, key] = value
        df.to_csv(self.path, index=False)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_data_store.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add data_store.py tests/test_data_store.py
git commit -m "feat: transaction data store with deduplication"
```

---

### Task 3: Auto-Categorizer

**Files:**
- Create: `finance-tracker/categorizer.py`
- Create: `finance-tracker/tests/test_categorizer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_categorizer.py`:

```python
import pytest
from categorizer import Categorizer

@pytest.fixture
def cat():
    return Categorizer(config_path="config.json")

def test_categorizes_food(cat):
    assert cat.categorize("CHIPOTLE #1234") == "Food & Dining"

def test_categorizes_transport(cat):
    assert cat.categorize("UBER TRIP") == "Transport"

def test_categorizes_subscriptions(cat):
    assert cat.categorize("NETFLIX.COM") == "Subscriptions"

def test_categorizes_income(cat):
    assert cat.categorize("DIRECT DEPOSIT PAYROLL") == "Income"

def test_unknown_merchant_returns_other(cat):
    assert cat.categorize("RANDOM UNKNOWN MERCHANT XYZ") == "Other"

def test_case_insensitive(cat):
    assert cat.categorize("chipotle mexican grill") == "Food & Dining"

def test_normalizes_merchant_name(cat):
    # Strips branch suffixes like #1234
    from categorizer import normalize_merchant
    assert normalize_merchant("CHIPOTLE #1234") == "chipotle"
    assert normalize_merchant("UBER* TRIP") == "uber trip"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_categorizer.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'categorizer'`

- [ ] **Step 3: Implement `categorizer.py`**

```python
import re
import json

def normalize_merchant(name: str) -> str:
    name = name.lower()
    name = re.sub(r'#\d+', '', name)      # strip branch numbers
    name = re.sub(r'\*', ' ', name)        # replace * with space
    name = re.sub(r'\s+', ' ', name)       # collapse whitespace
    return name.strip()

class Categorizer:
    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            config = json.load(f)
        self.categories = config["categories"]

    def categorize(self, merchant: str) -> str:
        normalized = normalize_merchant(merchant)
        for category, keywords in self.categories.items():
            if category == "Other":
                continue
            for keyword in keywords:
                if keyword in normalized:
                    return category
        return "Other"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_categorizer.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add categorizer.py tests/test_categorizer.py
git commit -m "feat: keyword-based transaction categorizer"
```

---

## Chunk 2: Importers (CSV + PDF)

### Task 4: CSV Importer

**Files:**
- Create: `finance-tracker/importers/__init__.py`
- Create: `finance-tracker/importers/csv_parser.py`
- Create: `finance-tracker/tests/test_csv_parser.py`
- Create: `finance-tracker/tests/fixtures/chase_sample.csv`
- Create: `finance-tracker/tests/fixtures/amex_sample.csv`

- [ ] **Step 1: Create test fixture CSVs and `tests/__init__.py`**

Create `tests/__init__.py`: (empty file)

Create `tests/fixtures/chase_sample.csv`:
```
Transaction Date,Post Date,Description,Category,Type,Amount,Memo
01/15/2024,01/16/2024,CHIPOTLE #1234,Food & Drink,Sale,-45.20,
01/16/2024,01/17/2024,NETFLIX.COM,Entertainment,Sale,-15.99,
01/17/2024,01/18/2024,DIRECT DEPOSIT,Other,Payment,2500.00,
```

Create `tests/fixtures/amex_sample.csv`:
```
Date,Description,Amount
01/15/2024,CHIPOTLE MEXICAN GRILL,45.20
01/16/2024,SPOTIFY USA,9.99
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_csv_parser.py`:

```python
import pytest
import pandas as pd
from importers.csv_parser import CSVParser

@pytest.fixture
def parser():
    return CSVParser(config_path="config.json")

def test_parse_chase_csv(parser):
    txs = parser.parse("tests/fixtures/chase_sample.csv", bank="chase", account="Chase-Checking")
    assert len(txs) == 3
    assert txs[0]["merchant"] == "chipotle"
    assert txs[0]["amount"] == -45.20
    assert txs[0]["account"] == "Chase-Checking"
    assert txs[0]["source"] == "csv"

def test_parse_amex_csv_inverts_sign(parser):
    txs = parser.parse("tests/fixtures/amex_sample.csv", bank="amex", account="Amex-Credit")
    assert txs[0]["amount"] == -45.20  # Amex exports positive, we invert

def test_all_transactions_have_ids(parser):
    txs = parser.parse("tests/fixtures/chase_sample.csv", bank="chase", account="Chase-Checking")
    for tx in txs:
        assert "id" in tx and len(tx["id"]) == 16

def test_transactions_have_categories(parser):
    txs = parser.parse("tests/fixtures/chase_sample.csv", bank="chase", account="Chase-Checking")
    merchants = {tx["merchant"]: tx["category"] for tx in txs}
    assert merchants["chipotle"] == "Food & Dining"
    assert merchants["netflix.com"] == "Subscriptions"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_csv_parser.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement `importers/__init__.py`**

```python
# empty
```

- [ ] **Step 5: Implement `importers/csv_parser.py`**

```python
import json
import pandas as pd
from categorizer import Categorizer, normalize_merchant
from data_store import generate_id

class CSVParser:
    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            config = json.load(f)
        self.formats = config["bank_formats"]
        self.cat = Categorizer(config_path)

    def parse(self, filepath: str, bank: str, account: str) -> list[dict]:
        fmt = self.formats[bank]
        df = pd.read_csv(filepath)

        transactions = []
        for _, row in df.iterrows():
            raw_merchant = str(row[fmt["merchant_col"]])
            raw_amount = float(str(row[fmt["amount_col"]]).replace(",", "").replace("$", ""))
            raw_date = pd.to_datetime(row[fmt["date_col"]]).strftime("%Y-%m-%d")

            amount = -abs(raw_amount) if fmt["amount_sign"] == "inverted" else raw_amount
            merchant = normalize_merchant(raw_merchant)

            tx = {
                "id": generate_id(raw_date, amount, merchant, account),
                "date": raw_date,
                "amount": amount,
                "merchant": merchant,
                "category": self.cat.categorize(raw_merchant),
                "account": account,
                "source": "csv",
                "is_income": False,
                "is_savings": False,
                "notes": ""
            }
            transactions.append(tx)
        return transactions
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_csv_parser.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add importers/ tests/test_csv_parser.py tests/fixtures/
git commit -m "feat: CSV importer with per-bank format profiles"
```

---

### Task 5: PDF Importer

**Files:**
- Create: `finance-tracker/importers/pdf_parser.py`
- Create: `finance-tracker/tests/test_pdf_parser.py`

> Note: PDF parsing is the highest-risk task in Phase 1. Each bank has a different statement layout. Tests here use small hand-crafted PDFs created with `reportlab` (a test dependency) to avoid needing real bank statements in the repo.

- [ ] **Step 1: Add reportlab to requirements.txt (test only)**

Append to `requirements.txt`:
```
reportlab==4.1.0
```

Run: `pip install reportlab`

- [ ] **Step 2: Create PDF fixture generator**

Create `tests/fixtures/make_pdf_fixtures.py`:

```python
"""Run once to generate PDF fixtures for tests: python tests/fixtures/make_pdf_fixtures.py"""
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors

def make_chase_pdf(path):
    doc = SimpleDocTemplate(path, pagesize=letter)
    data = [
        ["Transaction Date", "Description", "Amount"],
        ["01/15/2024", "CHIPOTLE #1234", "-45.20"],
        ["01/16/2024", "NETFLIX.COM", "-15.99"],
        ["01/17/2024", "DIRECT DEPOSIT", "2500.00"],
    ]
    table = Table(data)
    table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.grey)]))
    doc.build([table])

if __name__ == "__main__":
    make_chase_pdf("tests/fixtures/chase_sample.pdf")
    print("PDF fixtures created.")
```

Run: `python tests/fixtures/make_pdf_fixtures.py`

- [ ] **Step 3: Write failing tests**

Create `tests/test_pdf_parser.py`:

```python
import pytest
from importers.pdf_parser import PDFParser

@pytest.fixture
def parser():
    return PDFParser(config_path="config.json")

def test_parse_chase_pdf_extracts_transactions(parser):
    txs = parser.parse("tests/fixtures/chase_sample.pdf", bank="chase", account="Chase-Checking")
    assert len(txs) == 3

def test_parsed_amounts_are_floats(parser):
    txs = parser.parse("tests/fixtures/chase_sample.pdf", bank="chase", account="Chase-Checking")
    for tx in txs:
        assert isinstance(tx["amount"], float)

def test_parsed_transactions_have_ids(parser):
    txs = parser.parse("tests/fixtures/chase_sample.pdf", bank="chase", account="Chase-Checking")
    for tx in txs:
        assert "id" in tx and len(tx["id"]) == 16
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
pytest tests/test_pdf_parser.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 5: Implement `importers/pdf_parser.py`**

```python
import re
import pdfplumber
import pandas as pd
from categorizer import Categorizer, normalize_merchant
from data_store import generate_id

class PDFParser:
    def __init__(self, config_path: str = "config.json"):
        self.cat = Categorizer(config_path)

    def parse(self, filepath: str, bank: str, account: str) -> list[dict]:
        if bank in ("chase", "bofa"):
            return self._parse_table(filepath, bank, account)
        elif bank == "amex":
            return self._parse_regex(filepath, account)
        else:
            return self._parse_table(filepath, bank, account)  # fallback

    def _parse_table(self, filepath: str, bank: str, account: str) -> list[dict]:
        transactions = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if not table or len(table) < 2:
                    continue
                headers = [str(h).strip() for h in table[0]]
                for row in table[1:]:
                    if not row or not any(row):
                        continue
                    row_dict = dict(zip(headers, [str(c).strip() if c else "" for c in row]))
                    tx = self._normalize_row(row_dict, bank, account, source="pdf")
                    if tx:
                        transactions.append(tx)
        return transactions

    def _parse_regex(self, filepath: str, account: str) -> list[dict]:
        # Amex line format: MM/DD/YYYY   MERCHANT NAME   AMOUNT
        pattern = re.compile(r'(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([\d,]+\.\d{2})')
        transactions = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for match in pattern.finditer(text):
                    date_str = pd.to_datetime(match.group(1)).strftime("%Y-%m-%d")
                    raw_merchant = match.group(2).strip()
                    amount = -float(match.group(3).replace(",", ""))  # Amex inverts
                    merchant = normalize_merchant(raw_merchant)
                    tx = {
                        "id": generate_id(date_str, amount, merchant, account),
                        "date": date_str,
                        "amount": amount,
                        "merchant": merchant,
                        "category": self.cat.categorize(raw_merchant),
                        "account": account,
                        "source": "pdf",
                        "is_income": False,
                        "is_savings": False,
                        "notes": ""
                    }
                    transactions.append(tx)
        return transactions

    def _normalize_row(self, row: dict, bank: str, account: str, source: str):
        try:
            if bank == "chase":
                date_str = pd.to_datetime(row.get("Transaction Date", "")).strftime("%Y-%m-%d")
                raw_merchant = row.get("Description", "")
                amount = float(row.get("Amount", "0").replace(",", "").replace("$", ""))
            elif bank == "bofa":
                date_str = pd.to_datetime(row.get("Date", "")).strftime("%Y-%m-%d")
                raw_merchant = row.get("Description", "")
                amount = float(row.get("Amount", "0").replace(",", "").replace("$", ""))
            else:
                return None

            merchant = normalize_merchant(raw_merchant)
            return {
                "id": generate_id(date_str, amount, merchant, account),
                "date": date_str,
                "amount": amount,
                "merchant": merchant,
                "category": self.cat.categorize(raw_merchant),
                "account": account,
                "source": source,
                "is_income": False,
                "is_savings": False,
                "notes": ""
            }
        except Exception:
            return None
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_pdf_parser.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add importers/pdf_parser.py tests/test_pdf_parser.py tests/fixtures/make_pdf_fixtures.py tests/fixtures/chase_sample.pdf
git commit -m "feat: PDF importer for Chase/BofA (table) and Amex (regex)"
```

---

## Chunk 3: CLI Entry Point

### Task 6: `finance.py` CLI — Import & Manual Entry Commands

**Files:**
- Create: `finance-tracker/finance.py`
- Create: `finance-tracker/tests/test_cli_import.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_cli_import.py`:

```python
import pytest
from click.testing import CliRunner
from finance import cli

@pytest.fixture
def runner():
    return CliRunner()

def test_import_csv_command_succeeds(runner, tmp_path):
    # Copy fixture to tmp dir
    import shutil
    csv_path = "tests/fixtures/chase_sample.csv"
    result = runner.invoke(cli, [
        "import", "csv", csv_path,
        "--account", "Chase-Checking",
        "--bank", "chase",
        "--data-dir", str(tmp_path)
    ])
    assert result.exit_code == 0
    assert "Imported" in result.output

def test_import_csv_skips_duplicates(runner, tmp_path):
    csv_path = "tests/fixtures/chase_sample.csv"
    runner.invoke(cli, ["import", "csv", csv_path, "--account", "Chase-Checking", "--bank", "chase", "--data-dir", str(tmp_path)])
    result = runner.invoke(cli, ["import", "csv", csv_path, "--account", "Chase-Checking", "--bank", "chase", "--data-dir", str(tmp_path)])
    # All 3 transactions are duplicates — should import 0 new
    assert "0 new" in result.output

def test_add_manual_transaction(runner, tmp_path):
    result = runner.invoke(cli, [
        "add",
        "--amount", "-45.20",
        "--merchant", "Chipotle",
        "--account", "Chase-Checking",
        "--data-dir", str(tmp_path)
    ])
    assert result.exit_code == 0
    assert "Added" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_cli_import.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'finance'`

- [ ] **Step 3: Implement `finance.py` (import + add commands)**

```python
import click
from rich.console import Console
from rich.table import Table
from data_store import DataStore
from categorizer import Categorizer
from importers.csv_parser import CSVParser
from importers.pdf_parser import PDFParser
from data_store import generate_id
import json
import os

console = Console()

@click.group()
def cli():
    """Personal finance tracker."""
    pass

# ── import ────────────────────────────────────────────────────────────────────

@cli.group()
def import_cmd():
    """Import transactions from a file."""
    pass

cli.add_command(import_cmd, name="import")

@import_cmd.command("csv")
@click.argument("filepath")
@click.option("--account", required=True, help="Account name (e.g. Chase-Checking)")
@click.option("--bank", required=True, type=click.Choice(["chase", "bofa", "amex"]))
@click.option("--data-dir", default="data", hidden=True)
def import_csv(filepath, account, bank, data_dir):
    """Import a CSV bank statement."""
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    parser = CSVParser()
    transactions = parser.parse(filepath, bank=bank, account=account)
    added, skipped = 0, 0
    for tx in transactions:
        if store.is_duplicate(tx):
            skipped += 1
        else:
            store.add(tx)
            added += 1
    console.print(f"[green]Imported {added} new transactions[/green] ({skipped} skipped as duplicates)")

@import_cmd.command("pdf")
@click.argument("filepath")
@click.option("--account", required=True, help="Account name (e.g. Chase-Checking)")
@click.option("--bank", required=True, type=click.Choice(["chase", "bofa", "amex"]))
@click.option("--data-dir", default="data", hidden=True)
def import_pdf(filepath, account, bank, data_dir):
    """Import a PDF bank statement."""
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    parser = PDFParser()
    transactions = parser.parse(filepath, bank=bank, account=account)
    added, skipped = 0, 0
    for tx in transactions:
        if store.is_duplicate(tx):
            skipped += 1
        else:
            store.add(tx)
            added += 1
    console.print(f"[green]Imported {added} new transactions[/green] ({skipped} skipped as duplicates)")

# ── add ───────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--amount", required=True, type=float, help="Amount (negative = expense)")
@click.option("--merchant", required=True)
@click.option("--account", required=True)
@click.option("--category", default=None)
@click.option("--notes", default="")
@click.option("--income", is_flag=True)
@click.option("--savings", is_flag=True)
@click.option("--data-dir", default="data", hidden=True)
def add(amount, merchant, account, category, notes, income, savings, data_dir):
    """Manually add a transaction."""
    from datetime import date
    cat = Categorizer() if category is None else None
    date_str = date.today().isoformat()
    resolved_category = category or (cat.categorize(merchant) if cat else "Other")
    tx = {
        "id": generate_id(date_str, amount, merchant, account),
        "date": date_str,
        "amount": amount,
        "merchant": merchant,
        "category": resolved_category,
        "account": account,
        "source": "manual",
        "is_income": income,
        "is_savings": savings,
        "notes": notes
    }
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    if store.is_duplicate(tx):
        console.print("[yellow]Transaction already exists, skipped.[/yellow]")
    else:
        store.add(tx)
        console.print(f"[green]Added:[/green] {merchant} {amount:+.2f} → {resolved_category}")

if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_cli_import.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add finance.py tests/test_cli_import.py
git commit -m "feat: CLI import (csv/pdf) and manual add commands"
```

---

### Task 7: CLI — Summary, Net Worth & Tag Commands

**Files:**
- Modify: `finance-tracker/finance.py`
- Create: `finance-tracker/tests/test_cli_summary.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_cli_summary.py`:

```python
import pytest
import os
from click.testing import CliRunner
from finance import cli

@pytest.fixture
def runner_with_data(tmp_path):
    runner = CliRunner()
    # Seed with known transactions
    txs = [
        ["--amount", "-45.20", "--merchant", "Chipotle", "--account", "Chase-Checking", "--data-dir", str(tmp_path)],
        ["--amount", "-15.99", "--merchant", "Netflix", "--account", "Chase-Checking", "--data-dir", str(tmp_path)],
        ["--amount", "2500.00", "--merchant", "Payroll", "--account", "Chase-Checking", "--income", "--data-dir", str(tmp_path)],
    ]
    for args in txs:
        runner.invoke(cli, ["add"] + args)
    return runner, tmp_path

def test_summary_shows_income_and_expenses(runner_with_data):
    runner, tmp_path = runner_with_data
    result = runner.invoke(cli, ["summary", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "2500" in result.output
    assert "61" in result.output  # 45.20 + 15.99

def test_networth_command_runs(runner_with_data):
    runner, tmp_path = runner_with_data
    # Create accounts.json
    import json
    accounts = {"accounts": [{"name": "Chase-Checking", "type": "checking", "institution": "Chase",
                               "balance": 4200.00, "currency": "USD", "last_updated": "2024-01-15"}]}
    (tmp_path / "accounts.json").write_text(json.dumps(accounts))
    result = runner.invoke(cli, ["networth", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "4200" in result.output

def test_spending_command_filters_by_category(runner_with_data):
    runner, tmp_path = runner_with_data
    result = runner.invoke(cli, ["spending", "--category", "Food & Dining", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Chipotle" in result.output or "chipotle" in result.output

def test_tag_income_command(runner_with_data):
    runner, tmp_path = runner_with_data
    import pandas as pd
    df = pd.read_csv(tmp_path / "transactions.csv")
    tx_id = df.iloc[0]["id"]
    result = runner.invoke(cli, ["tag", tx_id, "--income", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    df2 = pd.read_csv(tmp_path / "transactions.csv")
    row = df2[df2["id"] == tx_id].iloc[0]
    assert str(row["is_income"]).lower() == "true"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_cli_summary.py -v
```

Expected: FAIL — `summary`, `networth`, `tag` commands not yet defined.

- [ ] **Step 3: Add summary, networth, tag, and account commands to `finance.py`**

Append to `finance.py` (before `if __name__ == "__main__":`):

```python
# ── summary ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--month", default=None, help="YYYY-MM (defaults to current month)")
@click.option("--data-dir", default="data", hidden=True)
def summary(month, data_dir):
    """Show income vs expenses for a month."""
    import pandas as pd
    from datetime import date
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    df = store.load()
    if df.empty:
        console.print("[yellow]No transactions found.[/yellow]")
        return
    target_month = month or date.today().strftime("%Y-%m")
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"].dt.strftime("%Y-%m") == target_month]
    income = df[df["amount"] > 0]["amount"].sum()
    expenses = df[df["amount"] < 0]["amount"].sum()
    saved = income + expenses
    t = Table(title=f"Summary — {target_month}", show_header=True)
    t.add_column("", style="bold")
    t.add_column("Amount", justify="right")
    t.add_row("Income", f"[green]${income:,.2f}[/green]")
    t.add_row("Expenses", f"[red]${abs(expenses):,.2f}[/red]")
    t.add_row("Saved", f"[cyan]${saved:,.2f}[/cyan]")
    console.print(t)

# ── top-categories ────────────────────────────────────────────────────────────

@cli.command("top-categories")
@click.option("--last", default="1month", help="e.g. 1month, 3months")
@click.option("--data-dir", default="data", hidden=True)
def top_categories(last, data_dir):
    """Show spending ranked by category."""
    import pandas as pd
    from datetime import date, timedelta
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    df = store.load()
    if df.empty:
        console.print("[yellow]No transactions found.[/yellow]")
        return
    months = int(last.replace("months", "").replace("month", ""))
    cutoff = (date.today() - timedelta(days=30 * months)).isoformat()
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= cutoff) & (df["amount"] < 0)]
    by_cat = df.groupby("category")["amount"].sum().abs().sort_values(ascending=False)
    t = Table(title=f"Top Categories (last {months} month(s))", show_header=True)
    t.add_column("Category")
    t.add_column("Total", justify="right")
    for cat, total in by_cat.items():
        t.add_row(cat, f"${total:,.2f}")
    console.print(t)

# ── spending ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--category", required=True)
@click.option("--year", default=None, help="YYYY — filter to a specific year")
@click.option("--data-dir", default="data", hidden=True)
def spending(category, year, data_dir):
    """Drill into spending for a specific category."""
    import pandas as pd
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    df = store.load()
    if df.empty:
        console.print("[yellow]No transactions found.[/yellow]")
        return
    df["date"] = pd.to_datetime(df["date"])
    mask = (df["category"].str.lower() == category.lower()) & (df["amount"] < 0)
    if year:
        mask &= df["date"].dt.year == int(year)
    subset = df[mask].sort_values("date", ascending=False)
    if subset.empty:
        console.print(f"[yellow]No transactions found for category '{category}'.[/yellow]")
        return
    t = Table(title=f"Spending — {category}{' (' + year + ')' if year else ''}", show_header=True)
    t.add_column("Date")
    t.add_column("Merchant")
    t.add_column("Amount", justify="right")
    for _, row in subset.iterrows():
        t.add_row(str(row["date"].date()), row["merchant"], f"[red]${abs(row['amount']):,.2f}[/red]")
    total = subset["amount"].sum()
    t.add_row("", "[bold]TOTAL[/bold]", f"[bold red]${abs(total):,.2f}[/bold red]")
    console.print(t)

# ── networth ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--data-dir", default="data", hidden=True)
def networth(data_dir):
    """Show net worth across all accounts."""
    accounts_path = f"{data_dir}/accounts.json"
    if not os.path.exists(accounts_path):
        console.print("[yellow]No accounts.json found. Run: finance account update <name> --balance <n>[/yellow]")
        return
    with open(accounts_path) as f:
        data = json.load(f)
    accounts = data.get("accounts", [])
    total = sum(a["balance"] for a in accounts)
    t = Table(title="Net Worth", show_header=True)
    t.add_column("Account")
    t.add_column("Type")
    t.add_column("Balance", justify="right")
    for a in accounts:
        t.add_row(a["name"], a["type"], f"${a['balance']:,.2f}")
    t.add_row("", "[bold]TOTAL[/bold]", f"[bold green]${total:,.2f}[/bold green]")
    console.print(t)

# ── account ───────────────────────────────────────────────────────────────────

@cli.group()
def account():
    """Manage accounts."""
    pass

@account.command("update")
@click.argument("name")
@click.option("--balance", required=True, type=float)
@click.option("--type", "account_type", default="checking",
              type=click.Choice(["checking", "savings", "credit", "investment"]))
@click.option("--data-dir", default="data", hidden=True)
def account_update(name, balance, account_type, data_dir):
    """Update or create an account balance."""
    from datetime import date
    accounts_path = f"{data_dir}/accounts.json"
    if os.path.exists(accounts_path):
        with open(accounts_path) as f:
            data = json.load(f)
    else:
        data = {"accounts": []}
    accounts = data["accounts"]
    existing = next((a for a in accounts if a["name"] == name), None)
    if existing:
        existing["balance"] = balance
        existing["last_updated"] = date.today().isoformat()
    else:
        accounts.append({"name": name, "type": account_type, "institution": name.split("-")[0],
                          "balance": balance, "currency": "USD", "last_updated": date.today().isoformat()})
    with open(accounts_path, "w") as f:
        json.dump(data, f, indent=2)
    console.print(f"[green]Updated {name}: ${balance:,.2f}[/green]")

# ── tag ───────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("transaction_id")
@click.option("--income", is_flag=True)
@click.option("--savings", is_flag=True)
@click.option("--data-dir", default="data", hidden=True)
def tag(transaction_id, income, savings, data_dir):
    """Tag a transaction as income or savings."""
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    fields = {}
    if income:
        fields["is_income"] = True
    if savings:
        fields["is_savings"] = True
    if not fields:
        console.print("[yellow]Specify --income or --savings[/yellow]")
        return
    store.update(transaction_id, fields)
    console.print(f"[green]Tagged transaction {transaction_id[:8]}...[/green]")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_cli_summary.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add finance.py tests/test_cli_summary.py
git commit -m "feat: summary, networth, tag, and account CLI commands"
```

---

## Chunk 4: Savings Goals + Dashboard

### Task 8: Goals CLI Commands

**Files:**
- Create: `finance-tracker/goals.py`
- Modify: `finance-tracker/finance.py`
- Create: `finance-tracker/tests/test_goals.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_goals.py`:

```python
import pytest
import json
from click.testing import CliRunner
from finance import cli

@pytest.fixture
def runner():
    return CliRunner()

def test_set_monthly_goal(runner, tmp_path):
    result = runner.invoke(cli, ["goal", "set", "monthly", "--amount", "500", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    goals = json.loads((tmp_path / "goals.json").read_text())
    assert goals["monthly_target"] == 500.0

def test_set_named_goal(runner, tmp_path):
    result = runner.invoke(cli, ["goal", "set", "Emergency Fund", "--target", "10000", "--by", "2025-06", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    goals = json.loads((tmp_path / "goals.json").read_text())
    assert goals["goals"][0]["name"] == "Emergency Fund"
    assert goals["goals"][0]["target_amount"] == 10000.0

def test_goal_status_shows_progress(runner, tmp_path):
    runner.invoke(cli, ["goal", "set", "Emergency Fund", "--target", "10000", "--by", "2025-06", "--data-dir", str(tmp_path)])
    result = runner.invoke(cli, ["goal", "status", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Emergency Fund" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_goals.py -v
```

Expected: FAIL — `goal` command not defined.

- [ ] **Step 3: Implement `goals.py`**

```python
import json
import os
from datetime import date

DEFAULT_GOALS = {
    "monthly_target": 0.0,
    "goals": [],
    "monthly_streak": {"current": 0, "best": 0, "history": {}}
}

def load_goals(data_dir: str = "data") -> dict:
    path = f"{data_dir}/goals.json"
    if not os.path.exists(path):
        return DEFAULT_GOALS.copy()
    with open(path) as f:
        return json.load(f)

def save_goals(goals: dict, data_dir: str = "data") -> None:
    path = f"{data_dir}/goals.json"
    os.makedirs(data_dir, exist_ok=True)
    with open(path, "w") as f:
        json.dump(goals, f, indent=2)

def set_monthly_target(amount: float, data_dir: str = "data") -> None:
    goals = load_goals(data_dir)
    goals["monthly_target"] = amount
    save_goals(goals, data_dir)

def add_named_goal(name: str, target: float, deadline: str, data_dir: str = "data") -> None:
    goals = load_goals(data_dir)
    goals["goals"].append({
        "name": name,
        "target_amount": target,
        "current_amount": 0.0,
        "deadline": deadline,
        "created": date.today().isoformat()
    })
    save_goals(goals, data_dir)

def get_goal_progress(data_dir: str = "data") -> dict:
    return load_goals(data_dir)
```

- [ ] **Step 4: Add goal commands to `finance.py`**

Append to `finance.py` (before `if __name__ == "__main__":`):

```python
# ── goal ──────────────────────────────────────────────────────────────────────

from goals import set_monthly_target, add_named_goal, get_goal_progress

@cli.group()
def goal():
    """Manage savings goals."""
    pass

@goal.command("set")
@click.argument("name")
@click.option("--amount", type=float, default=None, help="Monthly savings target (use with 'monthly')")
@click.option("--target", type=float, default=None, help="Named goal target amount")
@click.option("--by", "deadline", default=None, help="Deadline YYYY-MM for named goal")
@click.option("--data-dir", default="data", hidden=True)
def goal_set(name, amount, target, deadline, data_dir):
    """Set a monthly savings target or a named goal."""
    if name == "monthly":
        if amount is None:
            console.print("[red]--amount required for monthly goal[/red]")
            return
        set_monthly_target(amount, data_dir)
        console.print(f"[green]Monthly savings target set: ${amount:,.2f}[/green]")
    else:
        if target is None or deadline is None:
            console.print("[red]--target and --by required for named goal[/red]")
            return
        add_named_goal(name, target, deadline, data_dir)
        console.print(f"[green]Goal '{name}' set: ${target:,.2f} by {deadline}[/green]")

@goal.command("status")
@click.option("--data-dir", default="data", hidden=True)
def goal_status(data_dir):
    """Show progress on all savings goals."""
    from datetime import date
    data = get_goal_progress(data_dir)
    monthly = data.get("monthly_target", 0)
    streak = data.get("monthly_streak", {})
    console.print(f"\n[bold]Monthly target:[/bold] ${monthly:,.2f}/month  |  Streak: {streak.get('current', 0)} months\n")
    goals = data.get("goals", [])
    if not goals:
        console.print("[yellow]No named goals set. Use: finance goal set \"Goal Name\" --target 5000 --by 2025-06[/yellow]")
        return
    t = Table(title="Savings Goals", show_header=True)
    t.add_column("Goal")
    t.add_column("Progress", justify="right")
    t.add_column("Target", justify="right")
    t.add_column("% Done", justify="right")
    t.add_column("Deadline")
    for g in goals:
        pct = (g["current_amount"] / g["target_amount"] * 100) if g["target_amount"] > 0 else 0
        t.add_row(g["name"], f"${g['current_amount']:,.2f}",
                  f"${g['target_amount']:,.2f}", f"{pct:.0f}%", g["deadline"])
    console.print(t)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_goals.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add goals.py finance.py tests/test_goals.py
git commit -m "feat: savings goals CLI (monthly target + named goals)"
```

---

### Task 9: HTML Dashboard Generator

**Files:**
- Create: `finance-tracker/dashboard.py`
- Create: `finance-tracker/templates/dashboard.html.j2`
- Modify: `finance-tracker/finance.py`
- Create: `finance-tracker/tests/test_dashboard.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_dashboard.py`:

```python
import pytest
import os
from click.testing import CliRunner
from finance import cli

@pytest.fixture
def runner_with_data(tmp_path):
    runner = CliRunner()
    txs = [
        ["--amount", "-45.20", "--merchant", "Chipotle", "--account", "Chase-Checking", "--data-dir", str(tmp_path)],
        ["--amount", "-15.99", "--merchant", "Netflix", "--account", "Chase-Checking", "--data-dir", str(tmp_path)],
        ["--amount", "2500.00", "--merchant", "Payroll", "--account", "Chase-Checking", "--income", "--data-dir", str(tmp_path)],
    ]
    for args in txs:
        runner.invoke(cli, ["add"] + args)
    import json
    accounts = {"accounts": [{"name": "Chase-Checking", "type": "checking", "institution": "Chase",
                               "balance": 4200.00, "currency": "USD", "last_updated": "2024-01-15"}]}
    (tmp_path / "accounts.json").write_text(json.dumps(accounts))
    return runner, tmp_path

def test_dashboard_generates_html_file(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    result = runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    assert result.exit_code == 0
    assert os.path.exists(out_path)

def test_dashboard_html_contains_net_worth(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    assert "4,200" in content or "4200" in content

def test_dashboard_is_self_contained(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    # No external CDN links
    assert "cdn.jsdelivr.net" not in content
    assert "cdnjs.cloudflare.com" not in content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_dashboard.py -v
```

Expected: FAIL — `dashboard` command not defined.

- [ ] **Step 3: Download Chart.js for inline bundling**

```bash
curl -sL https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js -o templates/chart.min.js
```

- [ ] **Step 4: Create `templates/dashboard.html.j2`**

Create `templates/dashboard.html.j2`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Finance Dashboard</title>
<script>{{ chartjs }}</script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f1a; color: #e0e0e0; padding: 24px; }
  h1 { font-size: 1.5rem; margin-bottom: 24px; color: #fff; }
  h2 { font-size: 1rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }
  .card { background: #1a1a2e; border-radius: 10px; padding: 20px; }
  .card .value { font-size: 1.8rem; font-weight: 700; margin: 8px 0 4px; }
  .card .label { font-size: 0.75rem; color: #888; text-transform: uppercase; }
  .card .sub { font-size: 0.8rem; color: #888; }
  .green { color: #4ade80; }
  .red { color: #f87171; }
  .blue { color: #60a5fa; }
  .yellow { color: #facc15; }
  .chart-wrap { background: #1a1a2e; border-radius: 10px; padding: 20px; margin-bottom: 32px; }
  .chart-wrap canvas { max-height: 280px; }
  .insights { background: #1a1a2e; border-radius: 10px; padding: 20px; margin-bottom: 32px; }
  .insight { padding: 8px 0; border-bottom: 1px solid #2a2a3e; font-size: 0.9rem; }
  .insight:last-child { border-bottom: none; }
  .insight .icon { margin-right: 8px; }
  .goals-grid { display: grid; gap: 12px; margin-bottom: 32px; }
  .goal { background: #1a1a2e; border-radius: 10px; padding: 16px; }
  .goal .bar-bg { background: #2a2a3e; border-radius: 4px; height: 8px; margin: 8px 0 4px; }
  .goal .bar-fill { background: #60a5fa; border-radius: 4px; height: 8px; }
  .updated { font-size: 0.75rem; color: #555; text-align: right; margin-top: 16px; }
</style>
</head>
<body>
<h1>Finance Dashboard</h1>

<div class="grid">
  <div class="card">
    <div class="label">Net Worth</div>
    <div class="value green">${{ net_worth | format_currency }}</div>
    <div class="sub">{{ account_names }}</div>
  </div>
  <div class="card">
    <div class="label">This Month Income</div>
    <div class="value green">${{ income | format_currency }}</div>
  </div>
  <div class="card">
    <div class="label">This Month Expenses</div>
    <div class="value red">${{ expenses | format_currency }}</div>
  </div>
  <div class="card">
    <div class="label">Saved This Month</div>
    <div class="value blue">${{ saved | format_currency }}</div>
    {% if monthly_target > 0 %}
    <div class="sub {% if saved >= monthly_target %}green{% else %}red{% endif %}">
      Goal: ${{ monthly_target | format_currency }}/mo — {% if saved >= monthly_target %}on track{% else %}behind{% endif %}
    </div>
    {% endif %}
  </div>
</div>

<div class="chart-wrap">
  <h2>Spending by Category</h2>
  <canvas id="catChart"></canvas>
</div>

<div class="chart-wrap">
  <h2>Monthly Spending (Last 12 Months)</h2>
  <canvas id="trendChart"></canvas>
</div>

{% if goals %}
<h2>Savings Goals</h2>
<div class="goals-grid">
  {% for g in goals %}
  <div class="goal">
    <div style="display:flex;justify-content:space-between">
      <strong>{{ g.name }}</strong>
      <span class="blue">{{ g.pct }}%</span>
    </div>
    <div class="bar-bg"><div class="bar-fill" style="width:{{ [g.pct, 100] | min }}%"></div></div>
    <div class="sub">${{ g.current | format_currency }} / ${{ g.target | format_currency }} — by {{ g.deadline }}</div>
  </div>
  {% endfor %}
</div>
{% endif %}

{% if top_merchants %}
<div class="chart-wrap">
  <h2>Top Merchants This Month</h2>
  <table style="width:100%;border-collapse:collapse;font-size:0.85rem">
    <tr style="color:#888;border-bottom:1px solid #2a2a3e">
      <th style="text-align:left;padding:6px 0">Merchant</th>
      <th style="text-align:right;padding:6px 0">Spent</th>
    </tr>
    {% for m in top_merchants %}
    <tr style="border-bottom:1px solid #1a1a2e">
      <td style="padding:6px 0">{{ m.name }}</td>
      <td style="text-align:right;color:#f87171">${{ m.amount | format_currency }}</td>
    </tr>
    {% endfor %}
  </table>
</div>
{% endif %}

<div class="insights">
  <h2>Insights</h2>
  {% for insight in insights %}
  <div class="insight"><span class="icon">{{ insight.icon }}</span>{{ insight.text }}</div>
  {% endfor %}
</div>

<div class="updated">Last updated: {{ generated_at }}</div>

<script>
new Chart(document.getElementById('catChart'), {
  type: 'bar',
  data: {
    labels: {{ cat_labels | tojson }},
    datasets: [{
      label: 'Spending ($)',
      data: {{ cat_values | tojson }},
      backgroundColor: ['#f87171','#60a5fa','#a78bfa','#fb923c','#4ade80','#facc15','#38bdf8','#e879f9']
    }]
  },
  options: { responsive: true, plugins: { legend: { display: false } },
    scales: { x: { ticks: { color: '#aaa' }, grid: { color: '#2a2a3e' } },
               y: { ticks: { color: '#aaa' }, grid: { color: '#2a2a3e' } } } }
});
new Chart(document.getElementById('trendChart'), {
  type: 'line',
  data: {
    labels: {{ trend_labels | tojson }},
    datasets: [{
      label: 'Expenses ($)',
      data: {{ trend_values | tojson }},
      borderColor: '#f87171', backgroundColor: 'rgba(248,113,113,0.1)', fill: true, tension: 0.3
    }]
  },
  options: { responsive: true, plugins: { legend: { display: false } },
    scales: { x: { ticks: { color: '#aaa' }, grid: { color: '#2a2a3e' } },
               y: { ticks: { color: '#aaa' }, grid: { color: '#2a2a3e' } } } }
});
</script>
</body>
</html>
```

- [ ] **Step 5: Implement `dashboard.py`**

Create `dashboard.py`:

```python
import json
import os
import pandas as pd
from datetime import date, datetime, timedelta
from jinja2 import Environment, FileSystemLoader

import os as _os
_TEMPLATES_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "templates")

def build_dashboard(data_dir: str = "data", output_path: str = "reports/dashboard.html") -> str:
    store_path = f"{data_dir}/transactions.csv"
    accounts_path = f"{data_dir}/accounts.json"
    goals_path = f"{data_dir}/goals.json"

    try:
        df = pd.read_csv(store_path)
        df["date"] = pd.to_datetime(df["date"])
    except FileNotFoundError:
        df = pd.DataFrame()

    # Net worth
    net_worth = 0.0
    account_names = ""
    if os.path.exists(accounts_path):
        with open(accounts_path) as f:
            acct_data = json.load(f)
        accounts = acct_data.get("accounts", [])
        net_worth = sum(a["balance"] for a in accounts)
        account_names = " + ".join(a["name"] for a in accounts)

    # This month
    today = date.today()
    this_month = today.strftime("%Y-%m")
    if not df.empty:
        month_df = df[df["date"].dt.strftime("%Y-%m") == this_month]
        income = month_df[month_df["amount"] > 0]["amount"].sum()
        expenses = abs(month_df[month_df["amount"] < 0]["amount"].sum())
        saved = income - expenses
    else:
        income = expenses = saved = 0.0

    # Goals
    monthly_target = 0.0
    goals_display = []
    if os.path.exists(goals_path):
        with open(goals_path) as f:
            goals_data = json.load(f)
        monthly_target = goals_data.get("monthly_target", 0.0)
        for g in goals_data.get("goals", []):
            pct = int(g["current_amount"] / g["target_amount"] * 100) if g["target_amount"] > 0 else 0
            goals_display.append({
                "name": g["name"], "pct": pct,
                "current": g["current_amount"], "target": g["target_amount"],
                "deadline": g["deadline"]
            })

    # Category chart
    if not df.empty:
        expense_df = df[df["amount"] < 0]
        by_cat = expense_df.groupby("category")["amount"].sum().abs().sort_values(ascending=False)
        cat_labels = list(by_cat.index)
        cat_values = [round(v, 2) for v in by_cat.values]
    else:
        cat_labels, cat_values = [], []

    # 12-month trend (step back by calendar months, not days)
    trend_labels, trend_values = [], []
    for i in range(11, -1, -1):
        year = today.year + (today.month - 1 - i) // 12
        month = ((today.month - 1 - i) % 12) + 1
        label = f"{year:04d}-{month:02d}"
        trend_labels.append(label)
        if not df.empty:
            m_df = df[(df["date"].dt.strftime("%Y-%m") == label) & (df["amount"] < 0)]
            trend_values.append(round(abs(m_df["amount"].sum()), 2))
        else:
            trend_values.append(0)

    # Insights
    insights = []
    if cat_labels:
        insights.append({"icon": "💸", "text": f"Top spending category: {cat_labels[0]} (${cat_values[0]:,.2f})"})
    if monthly_target > 0:
        if saved >= monthly_target:
            insights.append({"icon": "✅", "text": f"Monthly savings goal hit! Saved ${saved:,.2f} vs ${monthly_target:,.2f} target."})
        else:
            insights.append({"icon": "⚠️", "text": f"Behind on monthly savings: ${saved:,.2f} of ${monthly_target:,.2f} target."})
    if len(trend_values) >= 2 and trend_values[-2] > 0:
        change = (trend_values[-1] - trend_values[-2]) / trend_values[-2] * 100
        if abs(change) >= 15:
            direction = "up" if change > 0 else "down"
            insights.append({"icon": "📈" if change > 0 else "📉",
                              "text": f"Total spending {direction} {abs(change):.0f}% vs last month."})
    if not df.empty:
        top_tx = df[df["amount"] < 0].nsmallest(1, "amount")
        if not top_tx.empty:
            row = top_tx.iloc[0]
            insights.append({"icon": "🔍", "text": f"Largest transaction: {row['merchant']} (${abs(row['amount']):,.2f})"})
    if not df.empty and "Subscriptions" in df["category"].values:
        sub_total = abs(df[(df["category"] == "Subscriptions") & (df["amount"] < 0)]["amount"].sum())
        if sub_total > 0:
            insights.append({"icon": "📺", "text": f"Total subscriptions: ${sub_total:,.2f}"})

    # Goals missed at current pace insight
    if goals_display and not df.empty:
        from datetime import datetime as _dt
        for g in goals_display:
            if g["pct"] < 100:
                months_left = max(1, (pd.to_datetime(g["deadline"] + "-01") - pd.Timestamp.today()).days // 30)
                needed_per_month = (g["target"] - g["current"]) / months_left
                if monthly_target > 0 and saved < needed_per_month:
                    insights.append({"icon": "🚨", "text": f"Goal '{g['name']}' may be missed — need ${needed_per_month:,.2f}/mo but saving ${saved:,.2f}/mo."})

    # Top merchants
    top_merchants = []
    if not df.empty:
        month_expense = df[(df["date"].dt.strftime("%Y-%m") == this_month) & (df["amount"] < 0)]
        tm = month_expense.groupby("merchant")["amount"].sum().abs().nlargest(10)
        top_merchants = [{"name": m, "amount": round(v, 2)} for m, v in tm.items()]

    # Render
    env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR))
    env.filters["format_currency"] = lambda v: f"{v:,.2f}"
    template = env.get_template("dashboard.html.j2")
    with open(os.path.join(_TEMPLATES_DIR, "chart.min.js")) as f:
        chartjs = f.read()

    html = template.render(
        net_worth=net_worth, account_names=account_names,
        income=income, expenses=expenses, saved=saved, monthly_target=monthly_target,
        goals=goals_display, cat_labels=cat_labels, cat_values=cat_values,
        trend_labels=trend_labels, trend_values=trend_values,
        top_merchants=top_merchants,
        insights=insights, generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        chartjs=chartjs
    )
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    return output_path
```

- [ ] **Step 6: Add `dashboard` command to `finance.py`**

Append to `finance.py`:

```python
# ── dashboard ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--output", default="reports/dashboard.html")
@click.option("--data-dir", default="data", hidden=True)
@click.option("--no-open", is_flag=True, hidden=True)
def dashboard(output, data_dir, no_open):
    """Generate and open the HTML dashboard."""
    from dashboard import build_dashboard
    path = build_dashboard(data_dir=data_dir, output_path=output)
    console.print(f"[green]Dashboard generated:[/green] {path}")
    if not no_open:
        import webbrowser
        webbrowser.open(f"file://{os.path.abspath(path)}")
```

- [ ] **Step 7: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add dashboard.py templates/ finance.py tests/test_dashboard.py
git commit -m "feat: HTML dashboard with net worth, categories, trends, and insights"
```

---

## Chunk 5: README & Final Polish

### Task 10: README

**Files:**
- Create: `finance-tracker/README.md`

- [ ] **Step 1: Create `README.md`** (write this file directly using the Write tool or a text editor — do not embed in a shell heredoc)

File contents:

    # Finance Tracker

A personal finance CLI with an auto-generated HTML dashboard. Tracks spending across Chase, BofA, Amex, and Robinhood.

## Prerequisites

- Python 3.10+
- pip

## Installation

```bash
git clone <repo>
cd finance-tracker
pip install -r requirements.txt
```

## Quick Start

### 1. Import your first bank statement

Download a CSV from your bank's website, then:

```bash
# Chase
python finance.py import csv ~/Downloads/Chase_Activity.csv --account Chase-Checking --bank chase

# Bank of America
python finance.py import csv ~/Downloads/BoA_Activity.csv --account BofA-Checking --bank bofa

# Amex
python finance.py import csv ~/Downloads/Amex_Activity.csv --account Amex-Credit --bank amex

# PDF statements work too
python finance.py import pdf ~/Downloads/Chase_Statement.pdf --account Chase-Checking --bank chase
```

### 2. Update your account balances (including Robinhood)

```bash
python finance.py account update Chase-Checking --balance 4200.00
python finance.py account update Robinhood --balance 12500.00 --type investment
```

### 3. Open the dashboard

```bash
python finance.py dashboard
```

## Command Reference

### Import
```bash
python finance.py import csv <file> --account <name> --bank [chase|bofa|amex]
python finance.py import pdf <file> --account <name> --bank [chase|bofa|amex]
```

### Manual Entry
```bash
python finance.py add --amount -45.20 --merchant "Chipotle" --account Chase-Checking
python finance.py add --amount 2500 --merchant "Payroll" --account Chase-Checking --income
```

### Analysis
```bash
python finance.py summary                         # This month
python finance.py summary --month 2024-01         # Specific month
python finance.py top-categories                  # Top spending categories
python finance.py top-categories --last 3months
```

### Net Worth
```bash
python finance.py networth
python finance.py account update Robinhood --balance 13000 --type investment
```

### Savings Goals
```bash
python finance.py goal set monthly --amount 500
python finance.py goal set "Emergency Fund" --target 10000 --by 2025-06
python finance.py goal status
```

### Tagging
```bash
python finance.py tag <transaction_id> --income    # Mark as income
python finance.py tag <transaction_id> --savings   # Mark as savings contribution
```

## Adding a New Bank Format

Edit `config.json` → `bank_formats`, add a new entry matching your bank's CSV column names.

## Phase 2: Plaid Integration

Coming soon. Will enable automatic transaction sync from all connected accounts. Add your Plaid keys to `.env` (never commit this file).

## Running Tests

```bash
pytest tests/ -v
```
```

- [ ] **Step 2: Run the full test suite one final time**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 3: Final commit**

```bash
git add README.md
git commit -m "docs: add README with quick start and full command reference"
```

---

## Summary

| Task | What it builds |
|------|---------------|
| 1 | Project scaffold, config, .gitignore |
| 2 | Transaction data store with deduplication |
| 3 | Keyword auto-categorizer |
| 4 | CSV importer with per-bank format profiles |
| 5 | PDF importer (table + regex per bank) |
| 6 | CLI import + manual add commands |
| 7 | CLI summary, networth, tag, account commands |
| 8 | Savings goals (monthly + named) |
| 9 | HTML dashboard (self-contained, offline) |
| 10 | README |
