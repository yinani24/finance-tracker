import pandas as pd
import pytest

from core.data_store import DataStore


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
        "notes": "",
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
        "notes": "",
    }
    tmp_store.add(tx)
    is_dup = tmp_store.is_duplicate(tx)
    assert is_dup is True


def test_duplicate_transaction_raises_on_add(tmp_store):
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
        "notes": "",
    }
    tmp_store.add(tx)
    with pytest.raises(ValueError):
        tmp_store.add(tx)  # second add should raise


def test_different_transaction_not_flagged_as_duplicate(tmp_store):
    tx1 = {
        "id": "abc123",
        "date": "2024-01-15",
        "amount": -45.20,
        "merchant": "Chipotle",
        "category": "Food & Dining",
        "account": "Chase-Checking",
        "source": "manual",
        "is_income": False,
        "is_savings": False,
        "notes": "",
    }
    tx2 = {
        "id": "def456",
        "date": "2024-01-16",
        "amount": -12.99,
        "merchant": "Netflix",
        "category": "Subscriptions",
        "account": "BofA-Credit",
        "source": "manual",
        "is_income": False,
        "is_savings": False,
        "notes": "",
    }
    tmp_store.add(tx1)
    assert tmp_store.is_duplicate(tx2) is False


def test_update_transaction_field(tmp_store):
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
        "notes": "",
    }
    tmp_store.add(tx)
    tmp_store.update("abc123", {"is_income": True})
    df = tmp_store.load()
    assert df.iloc[0]["is_income"]


def test_update_nonexistent_id_raises(tmp_store):
    with pytest.raises(KeyError):
        tmp_store.update("nonexistent", {"is_income": True})
