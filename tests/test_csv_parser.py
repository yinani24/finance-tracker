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
    assert txs[0]["amount"] == -45.20  # Amex exports positive expenses, we invert

def test_parse_amex_csv_refund_stays_positive(parser):
    txs = parser.parse("tests/fixtures/amex_sample.csv", bank="amex", account="Amex-Credit")
    # Row 3 in fixture is a refund exported as -20.00; inverted should be +20.00
    refund = next(tx for tx in txs if "refund" in tx["merchant"])
    assert refund["amount"] == 20.00

def test_all_transactions_have_ids(parser):
    txs = parser.parse("tests/fixtures/chase_sample.csv", bank="chase", account="Chase-Checking")
    for tx in txs:
        assert "id" in tx and len(tx["id"]) == 16

def test_transactions_have_categories(parser):
    txs = parser.parse("tests/fixtures/chase_sample.csv", bank="chase", account="Chase-Checking")
    merchants = {tx["merchant"]: tx["category"] for tx in txs}
    assert merchants["chipotle"] == "Food & Dining"
    assert merchants["netflix.com"] == "Subscriptions"
