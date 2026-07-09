import hashlib


def generate_dedupe_hash(
    date: str, amount: float, merchant: str, account_id: int
) -> str:
    """Stable idempotency key for a single transaction.

    Shared by the Plaid-sync and statement-import paths so the two can never
    drift on how a transaction is fingerprinted. ``amount`` MUST be given in the
    Plaid "outflow-positive" convention (positive = money leaving the account),
    which is the same value Plaid feeds this hasher — so a CSV-imported row and
    its Plaid twin for the same purchase collapse to the same hash. The stored
    ``Transaction.amount`` uses the opposite sign (negative = spend), so callers
    negate before hashing.
    """
    raw = f"{date}|{amount}|{merchant}|{account_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
