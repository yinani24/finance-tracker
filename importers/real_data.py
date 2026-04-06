"""
Custom importers for real bank statements.

Handles Chase credit card, BofA Visa credit, BofA checking/savings,
Robinhood CSV, and Robinhood brokerage PDF statements.

Account names are loaded from config.json → import_accounts.
Statement file paths are loaded from statements_manifest.json (gitignored).

Run from the repo root:
    python3 -m importers.real_data
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
from core.categorizer import Categorizer
from core.data_store import DataStore, generate_id

# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_config(config_path: str = "config.json") -> dict[str, Any]:
    """Load and return config.json as a dict."""
    with open(config_path) as f:
        return json.load(f)


def _load_manifest(manifest_path: str = "statements_manifest.json") -> dict[str, Any]:
    """Load and return statements_manifest.json as a dict."""
    with open(manifest_path) as f:
        return json.load(f)


def normalize_merchant(name: str) -> str:
    """
    Normalize a raw merchant name for consistent matching.

    Args:
        name: Raw merchant name.

    Returns:
        Lowercase, branch-stripped, whitespace-collapsed string.
    """
    name = name.lower()
    name = re.sub(r"#\d+", "", name)
    name = re.sub(r"\*", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


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

    Args:
        store: DataStore instance.
        cat: Categorizer instance.
        date_str: Date as YYYY-MM-DD string.
        amount: Transaction amount (negative = expense, positive = income).
        merchant: Raw merchant name.
        account: Account name string.
        source: Import source ('pdf', 'csv', 'manual').
        notes: Optional free-text annotation.
        is_income: True for payroll/income transactions.
        is_savings: True for savings transfers.

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


# ── Chase Bank (Checking + Savings) ──────────────────────────────────────────

_SKIP_CHASE_BANK = re.compile(
    r"(Online Transfer|Payment To Chase Card|Beginning Balance|Ending Balance|"
    r"TRANSACTION DETAIL|DATE\s+DESCRIPTION)",
    re.IGNORECASE,
)


def parse_chase_bank_pdf(
    store: DataStore,
    cat: Categorizer,
    filepath: str,
    checking_account: str,
    savings_account: str,
    closing_year: int,
    closing_month: int,
) -> tuple[int, int]:
    """
    Parse a Chase Bank combined checking/savings PDF statement.

    The combined statement contains both CHASE SECURE CHECKING and
    CHASE SAVINGS sections in the same PDF. Internal transfers and
    credit card payments are skipped automatically.

    Args:
        store: DataStore instance.
        cat: Categorizer instance.
        filepath: Path to the Chase Bank combined PDF.
        checking_account: Account name for the checking account.
        savings_account: Account name for the savings account.
        closing_year: Statement closing year.
        closing_month: Statement closing month.

    Returns:
        (added, skipped) counts.
    """
    tx_re = re.compile(
        r"^(\d{2}/\d{2})(?:\s+\d{2}/\d{2})?\s+(.+?)\s+([-]?[\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$"
    )
    added, skipped = 0, 0
    current_account = None

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
                if "CHASE SECURE CHECKING" in line.upper():
                    current_account = checking_account
                    continue
                if "CHASE SAVINGS" in line.upper():
                    current_account = savings_account
                    continue
                if not current_account:
                    continue
                if _SKIP_CHASE_BANK.search(line):
                    continue
                m = tx_re.match(line)
                if not m:
                    continue
                try:
                    date_part = m.group(1)
                    desc = m.group(2).strip()
                    amount_str = m.group(3)
                    tx_month = int(date_part.split("/")[0])
                    tx_day = int(date_part.split("/")[1])
                    year = infer_year(tx_month, closing_year, closing_month)
                    date_str = f"{year}-{tx_month:02d}-{tx_day:02d}"
                    amount = float(amount_str.replace(",", ""))
                    is_income = bool(re.search(r"payroll|direct deposit", desc, re.I))
                    a, s = _add_tx(
                        store,
                        cat,
                        date_str,
                        amount,
                        desc,
                        current_account,
                        is_income=is_income,
                    )
                    added += a
                    skipped += s
                except Exception:
                    continue

    return added, skipped


# ── Amex High Yield Savings ───────────────────────────────────────────────────


def parse_amex_hysa_pdf(
    store: DataStore,
    cat: Categorizer,
    filepath: str,
    account: str,
) -> tuple[int, int]:
    """
    Parse an American Express High Yield Savings Account PDF statement.

    Imports interest payment and deposit transactions.

    Args:
        store: DataStore instance.
        cat: Categorizer instance.
        filepath: Path to the Amex HYSA PDF.
        account: Account name to tag transactions with.

    Returns:
        (added, skipped) counts.
    """
    tx_re = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+\$([\d,]+\.\d{2})\s+\$([\d,]+\.\d{2})\s*$")
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
                m = tx_re.match(line)
                if not m:
                    continue
                try:
                    date_str_raw, desc, amount_str = (m.group(1), m.group(2).strip(), m.group(3))
                    date_str = datetime.strptime(date_str_raw, "%m/%d/%Y").strftime("%Y-%m-%d")
                    amount = float(amount_str.replace(",", ""))
                    is_income = bool(re.search(r"interest|dividend", desc, re.I))
                    a, s = _add_tx(
                        store,
                        cat,
                        date_str,
                        amount,
                        desc,
                        account,
                        is_income=is_income,
                    )
                    added += a
                    skipped += s
                except Exception:
                    continue

    return added, skipped


# ── Chase Credit Card ─────────────────────────────────────────────────────────


def infer_year(tx_month: int, closing_year: int, closing_month: int) -> int:
    """
    Infer transaction year from the statement closing date.

    Chase statement lines only show MM/DD. If the transaction month is
    after the closing month, the transaction occurred in the prior year.

    Args:
        tx_month: Transaction month (1–12).
        closing_year: Statement closing year.
        closing_month: Statement closing month.

    Returns:
        Inferred 4-digit year.
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
        store: DataStore instance.
        cat: Categorizer instance.
        filepath: Path to the Chase PDF statement.
        account: Account name to tag transactions with.
        closing_year: Statement closing year (for year inference).
        closing_month: Statement closing month (for year inference).

    Returns:
        (added, skipped) counts.
    """
    tx_re = re.compile(r"^(\d{2}/\d{2})\s+(.+?)\s{2,}(-?[\d,]+\.\d{2})\s*$")
    tx_re2 = re.compile(r"^(\d{2}/\d{2})\s+(.+?)\s+(-?[\d,]+\.\d{2})\s*$")
    skip_re = re.compile(
        r"(EXCHG RATE|X 0\.\d+|^TOTAL|^PAYMENT|^PURCHASE$|^Interest|"
        r"^INTEREST|Date of|Merchant Name|ACCOUNT ACTIVITY|CONTINUED|"
        r"^2026 Totals|^Total f|^Total i|Your Annual|Minimum Payment|"
        r"Paying only|Balance on this|SCENARIO|New Balance|MMaannaaggee|"
        r"^www\.|^1-800|^P\.O\. Box|^Wilmington|^Carol Stream)",
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
                if re.search(r"\bX\s+0\.\d+|\(EXCHG", merchant_raw):
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
        r"^(\d{2}/\d{2})\s+\d{2}/\d{2}\s+(.+?)\s+\d{4}\s+\d{4}\s+(-?[\d,]+\.\d{2})\s*$"
    )
    skip_re = re.compile(
        r"(TOTAL PAYMENTS|TOTAL PURCHASES|TOTAL INTEREST|Interest Charged|"
        r"^2026 Totals|^Total fees|^Total interest|INTEREST CHARGED ON|"
        r"Transaction.*Date.*Description|Account Summary|^Transactions$)",
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
                    date_part, desc, amount_str = (m.group(1), m.group(2).strip(), m.group(3))
                    dt = datetime.strptime(date_part, "%m/%d/%y")
                    date_str = dt.strftime("%Y-%m-%d")
                    amount = float(amount_str.replace(",", ""))
                    is_income = bool(
                        re.search(
                            r"CENTAVO|PAYROLL|BKOFAMERICA.*DEPOSIT|Zelle payment from", desc, re.I
                        )
                    )
                    is_savings = bool(re.search(r"ROBINHOOD", desc, re.I))
                    if re.search(
                        r"JPMorgan Chase.*Ext Trnsfr|Online Banking.*to CHK|"
                        r"Online Banking.*from SAV|Online Banking.*to SAV|"
                        r"Online Banking.*from CHK|Online Banking.*payment to CRD",
                        desc,
                        re.I,
                    ):
                        continue
                    a, s = _add_tx(
                        store,
                        cat,
                        date_str,
                        amount,
                        desc,
                        current_account,
                        is_income=is_income,
                        is_savings=is_savings,
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
                datetime.strptime(date_str, "%Y-%m-%d")
                a, s = _add_tx(
                    store,
                    cat,
                    date_str,
                    amount,
                    desc,
                    account,
                    source="csv",
                    is_income=True,
                    notes="Robinhood interest",
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
                if re.search(
                    r"\bBuy\b|\bSell\b|\bSLIP\b|\bCDIV\b|Dividend Reinvest|Collateral", line, re.I
                ):
                    continue
                try:
                    if re.search(r"Crypto Money Movement", line, re.I):
                        amt_m = re.findall(r"\$([\d,.]+)", line)
                        if amt_m:
                            a, s = _add_tx(
                                store,
                                cat,
                                date_str,
                                -float(amt_m[-1].replace(",", "")),
                                "Crypto Transfer",
                                account,
                                notes="Crypto money movement",
                            )
                            added += a
                            skipped += s
                        continue
                    if re.search(r"Gold Subscription", line, re.I):
                        amt_m = re.findall(r"\$([\d,.]+)", line)
                        if amt_m:
                            a, s = _add_tx(
                                store,
                                cat,
                                date_str,
                                -float(amt_m[-1].replace(",", "")),
                                "Robinhood Gold Subscription",
                                account,
                                notes="Robinhood Gold fee",
                            )
                            added += a
                            skipped += s
                        continue
                    if re.search(r"Interest Payment|Brokerage-held Cash Interest", line, re.I):
                        amt_m = re.findall(r"\$([\d,.]+)", line)
                        if amt_m:
                            a, s = _add_tx(
                                store,
                                cat,
                                date_str,
                                float(amt_m[-1].replace(",", "")),
                                "Robinhood Interest",
                                account,
                                is_income=True,
                                notes="Robinhood interest",
                            )
                            added += a
                            skipped += s
                        continue
                    if re.search(r"\bCDIV\b|Cash Div", line, re.I):
                        amt_m = re.findall(r"\$([\d,.]+)", line)
                        if amt_m:
                            a, s = _add_tx(
                                store,
                                cat,
                                date_str,
                                float(amt_m[-1].replace(",", "")),
                                "Dividend",
                                account,
                                is_income=True,
                                notes="Robinhood dividend",
                            )
                            added += a
                            skipped += s
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
        data_dir: Directory containing data files.
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
            store,
            cat,
            entry["path"],
            accounts.get("chase_credit", "Chase-CreditCard"),
            entry["closing_year"],
            entry["closing_month"],
        )
        added += a
        skipped += s
        print(f"  Chase {entry['path']}: {a} added, {s} skipped")

    for entry in manifest.get("chase_bank", []):
        a, s = parse_chase_bank_pdf(
            store,
            cat,
            entry["path"],
            accounts.get("chase_bank_checking", "Chase-Checking"),
            accounts.get("chase_bank_savings", "Chase-Savings"),
            entry["closing_year"],
            entry["closing_month"],
        )
        added += a
        skipped += s
        print(f"  Chase Bank {entry['path']}: {a} added, {s} skipped")

    for entry in manifest.get("amex_hysa", []):
        a, s = parse_amex_hysa_pdf(
            store,
            cat,
            entry["path"],
            accounts.get("amex_hysa", "Amex-HYSA"),
        )
        added += a
        skipped += s
        print(f"  Amex HYSA {entry['path']}: {a} added, {s} skipped")

    for entry in manifest.get("bofa_visa", []):
        a, s = parse_bofa_credit_pdf(
            store,
            cat,
            entry["path"],
            accounts.get("bofa_visa", "BofA-Visa"),
            entry["year"],
        )
        added += a
        skipped += s
        print(f"  BofA Visa {entry['path']}: {a} added, {s} skipped")

    for entry in manifest.get("bofa_checking", []):
        a, s = parse_bofa_checking_pdf(store, cat, entry["path"])
        added += a
        skipped += s
        print(f"  BofA Checking {entry['path']}: {a} added, {s} skipped")

    for entry in manifest.get("robinhood_csv", []):
        a, s = parse_robinhood_csv(
            store,
            cat,
            entry["path"],
            accounts.get("robinhood", "Robinhood"),
        )
        added += a
        skipped += s
        print(f"  Robinhood CSV {entry['path']}: {a} added, {s} skipped")

    for entry in manifest.get("robinhood_pdf", []):
        a, s = parse_robinhood_pdf(
            store,
            cat,
            entry["path"],
            accounts.get("robinhood", "Robinhood"),
        )
        added += a
        skipped += s
        print(f"  Robinhood PDF {entry['path']}: {a} added, {s} skipped")

    return added, skipped


if __name__ == "__main__":  # pragma: no cover
    total_added, total_skipped = run_import()
    print(f"\n{'=' * 40}")
    print(f"TOTAL: {total_added} new transactions added, {total_skipped} duplicates skipped")
