import pytest

from core.categorizer import Categorizer


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
    from core.categorizer import normalize_merchant

    assert normalize_merchant("CHIPOTLE #1234") == "chipotle"
    assert normalize_merchant("UBER* TRIP") == "uber trip"


def test_uber_eats_beats_uber_transport(cat):
    assert cat.categorize("UBER EATS ORDER") == "Food & Dining"
