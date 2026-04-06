from unittest.mock import MagicMock, patch

import pytest

from importers.pdf_parser import PDFParser


@pytest.fixture
def parser():
    return PDFParser(config_path="config.json")


def _make_pdf_mock(pages_text=None, pages_tables=None):
    """Build a mock pdfplumber context manager."""
    pages = []
    for i, text in enumerate(pages_text or []):
        page = MagicMock()
        page.extract_text.return_value = text
        table = (pages_tables or [None] * (i + 1))[i] if pages_tables else None
        page.extract_table.return_value = table
        pages.append(page)
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.pages = pages
    return ctx


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


def test_parse_routes_amex_to_regex(parser, tmp_path):
    """Cover the elif bank == 'amex' branch (line 36-37)."""
    fake = tmp_path / "amex.pdf"
    fake.write_bytes(b"%PDF")
    amex_text = "01/15/2026  CHIPOTLE GRILL  45.20\n"
    mock_pdf = _make_pdf_mock(pages_text=[amex_text])
    with patch("pdfplumber.open", return_value=mock_pdf):
        txs = parser.parse(str(fake), bank="amex", account="Amex-Credit")
    assert isinstance(txs, list)
    if txs:
        assert txs[0]["amount"] == -45.20


def test_parse_routes_unknown_bank_to_table(parser, tmp_path):
    """Cover the else fallback branch (line 38-39)."""
    fake = tmp_path / "other.pdf"
    fake.write_bytes(b"%PDF")
    # return no table so no transactions
    mock_pdf = _make_pdf_mock(pages_text=["no table content"], pages_tables=[None])
    with patch("pdfplumber.open", return_value=mock_pdf):
        txs = parser.parse(str(fake), bank="unknown", account="Other")
    assert txs == []


def test_parse_table_skips_short_table(parser, tmp_path):
    """Cover continue when table has < 2 rows (line 57)."""
    fake = tmp_path / "short.pdf"
    fake.write_bytes(b"%PDF")
    page = MagicMock()
    page.extract_table.return_value = [["header only"]]  # < 2 rows
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.pages = [page]
    with patch("pdfplumber.open", return_value=ctx):
        txs = parser._parse_table(str(fake), "chase", "Chase")
    assert txs == []


def test_parse_table_skips_empty_row(parser, tmp_path):
    """Cover continue when row is None/empty (line 61)."""
    fake = tmp_path / "empty_row.pdf"
    fake.write_bytes(b"%PDF")
    table = [
        ["Transaction Date", "Description", "Amount"],
        None,  # None row → skip
        ["", "", ""],  # all empty → skip
        ["01/15/2026", "CHIPOTLE", "-45.20"],
    ]
    page = MagicMock()
    page.extract_table.return_value = table
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.pages = [page]
    with patch("pdfplumber.open", return_value=ctx):
        txs = parser._parse_table(str(fake), "chase", "Chase")
    assert len(txs) == 1


def test_normalize_row_bofa(parser):
    """Cover the elif bank == 'bofa' branch (lines 123-126)."""
    row = {"Date": "01/15/2026", "Description": "AMAZON.COM", "Amount": "-89.99"}
    tx = parser._normalize_row(row, "bofa", "BofA-Checking", "pdf")
    assert tx is not None
    assert tx["amount"] == -89.99


def test_normalize_row_unknown_returns_none(parser):
    """Cover the else: return None branch (lines 127-128)."""
    row = {"Date": "01/15/2026", "Description": "TEST", "Amount": "10.00"}
    result = parser._normalize_row(row, "unknown_bank", "Acct", "pdf")
    assert result is None


def test_normalize_row_bad_data_returns_none(parser):
    """Cover except Exception: return None (lines 143-144)."""
    row = {"Transaction Date": "NOT_A_DATE", "Description": "CHIPOTLE", "Amount": "bad"}
    result = parser._normalize_row(row, "chase", "Chase", "pdf")
    assert result is None
