"""Generic table-based PDF parser that extracts transactions from bank statement PDFs."""

from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from core.categorizer import Categorizer, normalize_merchant
from core.data_store import generate_id


class PDFParser:
    """Parses bank PDF statements using table extraction or regex depending on the bank."""

    def __init__(self, config_path: str = "config.json") -> None:
        """Initialise the parser with a categorizer loaded from the config file.

        Args:
            config_path: Path to the JSON config file containing categorization rules.
        """
        self.cat = Categorizer(config_path)

    def parse(self, filepath: str, bank: str, account: str) -> list[dict]:
        """Parse a PDF bank statement and return a list of normalised transaction dicts.

        Args:
            filepath: Path to the PDF file to parse.
            bank: Bank key that determines the parsing strategy
                  ("chase" and "bofa" use table extraction; "amex" uses regex).
            account: Account identifier string attached to every transaction.

        Returns:
            A list of transaction dicts, each with id, date, amount, merchant, category,
            account, source, is_income, is_savings, and notes keys.
        """
        if bank in ("chase", "bofa"):
            return self._parse_table(filepath, bank, account)
        elif bank == "amex":
            return self._parse_regex(filepath, account)
        else:
            return self._parse_table(filepath, bank, account)  # fallback

    def _parse_table(self, filepath: str, bank: str, account: str) -> list[dict]:
        """Extract transactions from a PDF using pdfplumber's table detection.

        Args:
            filepath: Path to the PDF file.
            bank: Bank key passed through to _normalize_row for column mapping.
            account: Account identifier string attached to every transaction.

        Returns:
            A list of transaction dicts successfully parsed from table rows across all pages.
        """
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
        """Extract Amex transactions from PDF text using a regex pattern.

        Args:
            filepath: Path to the PDF file.
            account: Account identifier string attached to every transaction.

        Returns:
            A list of transaction dicts matched from the Amex line format
            (MM/DD/YYYY   MERCHANT NAME   AMOUNT) across all pages.
        """
        # Amex line format: MM/DD/YYYY   MERCHANT NAME   AMOUNT
        pattern = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([\d,]+\.\d{2})")
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
                        "notes": "",
                    }
                    transactions.append(tx)
        return transactions

    def _normalize_row(self, row: dict, bank: str, account: str, source: str) -> dict | None:
        """Normalise a raw table row dict into a transaction dict for a given bank.

        Args:
            row: Dict mapping header names to cell values from the extracted table row.
            bank: Bank key used to select the correct column names ("chase" or "bofa").
            account: Account identifier string attached to the transaction.
            source: Source label string (e.g. "pdf") attached to the transaction.

        Returns:
            A transaction dict with id, date, amount, merchant, category, account, source,
            is_income, is_savings, and notes keys, or None if parsing fails or bank is unsupported.
        """
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
                "notes": "",
            }
        except Exception:
            return None
