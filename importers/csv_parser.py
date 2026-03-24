"""Parses CSV bank export files into a normalised list of transaction dicts."""
import json
import pandas as pd
from core.categorizer import Categorizer, normalize_merchant
from core.data_store import generate_id


class CSVParser:
    """Parses bank-specific CSV exports using format rules from config.json."""

    def __init__(self, config_path: str = "config.json") -> None:
        """Initialise the parser by loading bank format definitions and the categorizer.

        Args:
            config_path: Path to the JSON config file containing bank_formats and categorization rules.
        """
        with open(config_path) as f:
            config = json.load(f)
        self.formats = config["bank_formats"]
        self.cat = Categorizer(config_path)

    def parse(self, filepath: str, bank: str, account: str) -> list[dict]:
        """Parse a CSV file and return a list of normalised transaction dicts.

        Args:
            filepath: Path to the CSV file to parse.
            bank: Bank key (e.g. "chase", "bofa") used to look up the column format config.
            account: Account identifier string attached to every transaction.

        Returns:
            A list of transaction dicts, each with id, date, amount, merchant, category,
            account, source, is_income, is_savings, and notes keys.
        """
        fmt = self.formats[bank]
        df = pd.read_csv(filepath)

        transactions = []
        for _, row in df.iterrows():
            raw_merchant = str(row[fmt["merchant_col"]])
            raw_amount = float(str(row[fmt["amount_col"]]).replace(",", "").replace("$", ""))
            raw_date = pd.to_datetime(row[fmt["date_col"]]).strftime("%Y-%m-%d")

            amount = -raw_amount if fmt["amount_sign"] == "inverted" else raw_amount
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
