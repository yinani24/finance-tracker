"""Manages flat-file transaction storage backed by a CSV file."""

import hashlib
import os
import pandas as pd

COLUMNS = ["id", "date", "amount", "merchant", "category", "account",
           "source", "is_income", "is_savings", "notes"]


def generate_id(date: str, amount: float, merchant: str, account: str) -> str:
    """Return a 16-character SHA256 hex digest that uniquely identifies a transaction.

    Args:
        date: Transaction date string.
        amount: Transaction amount.
        merchant: Merchant name (lowercased and stripped before hashing).
        account: Account name (lowercased and stripped before hashing).

    Returns:
        First 16 hex characters of the SHA256 digest of the concatenated fields.
    """
    raw = f"{date}{amount}{merchant.lower().strip()}{account.lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class DataStore:
    """Persists and retrieves transactions stored in a CSV file."""

    def __init__(self, transactions_path: str = "data/transactions.csv") -> None:
        """Initialise the DataStore with the path to the transactions CSV.

        Args:
            transactions_path: Filesystem path to the CSV file used for storage.
        """
        self.path = transactions_path

    def load(self) -> pd.DataFrame:
        """Load all transactions from the CSV file.

        Returns:
            DataFrame containing all stored transactions, or an empty DataFrame
            with the correct columns if the file does not exist yet.
        """
        try:
            df = pd.read_csv(self.path, dtype={"id": str})
            return df
        except FileNotFoundError:
            return pd.DataFrame(columns=COLUMNS)

    def add(self, tx: dict) -> None:
        """Append a new transaction to the store.

        Args:
            tx: Dictionary representing the transaction; must contain an ``id`` key.

        Raises:
            ValueError: If a transaction with the same ``id`` already exists.
        """
        if self.is_duplicate(tx):
            raise ValueError(f"Transaction {tx['id']} already exists in the store")
        df = self.load()
        new_row = pd.DataFrame([tx])
        df = pd.concat([df, new_row], ignore_index=True)
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        df.to_csv(self.path, index=False)

    def is_duplicate(self, tx: dict) -> bool:
        """Check whether a transaction with the same id already exists in the store.

        Args:
            tx: Dictionary representing the transaction; must contain an ``id`` key.

        Returns:
            ``True`` if the id is already present, ``False`` otherwise.
        """
        df = self.load()
        if df.empty:
            return False
        return tx["id"] in df["id"].values

    def update(self, tx_id: str, fields: dict) -> None:
        """Update one or more fields of an existing transaction.

        Args:
            tx_id: The ``id`` of the transaction to update.
            fields: Mapping of column names to new values.

        Raises:
            KeyError: If no transaction with ``tx_id`` exists in the store.
        """
        df = self.load()
        if not (df["id"] == tx_id).any():
            raise KeyError(f"Transaction {tx_id} not found")
        for key, value in fields.items():
            df.loc[df["id"] == tx_id, key] = value
        df.to_csv(self.path, index=False)
