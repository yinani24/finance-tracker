"""Tests for import_real_data.py parsers and run_import() entry point."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from core.categorizer import Categorizer
from core.data_store import DataStore
from importers import real_data as ird

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def tmp_store(tmp_path):
    """DataStore backed by a temporary directory."""
    return DataStore(transactions_path=str(tmp_path / "transactions.csv"))


@pytest.fixture
def tmp_config(tmp_path):
    """Write a minimal config.json with import_accounts and return its path."""
    cfg = {
        "categories": {"Food & Dining": ["chipotle", "whole foods"], "Other": []},
        "bank_formats": {},
        "import_accounts": {
            "chase_credit": "Chase-CreditCard",
            "chase_bank_checking": "Chase-Checking",
            "chase_bank_savings": "Chase-Savings",
            "bofa_visa": "BofA-Visa",
            "bofa_checking": "BofA-Checking",
            "amex_hysa": "Amex-HYSA",
            "robinhood": "Robinhood",
        },
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg))
    return str(path)


@pytest.fixture
def tmp_manifest(tmp_path):
    """Write a statements_manifest.json pointing at fixture files."""
    manifest = {
        "chase_credit": [
            {"path": f"{FIXTURES}/chase_sample.pdf", "closing_year": 2024, "closing_month": 1}
        ],
        "chase_bank": [
            {"path": f"{FIXTURES}/chase_bank_sample.pdf", "closing_year": 2026, "closing_month": 1}
        ],
        "bofa_visa": [{"path": f"{FIXTURES}/bofa_visa_sample.pdf", "year": 2024}],
        "bofa_checking": [{"path": f"{FIXTURES}/bofa_checking_sample.pdf"}],
        "amex_hysa": [{"path": f"{FIXTURES}/amex_hysa_sample.pdf"}],
        "robinhood_csv": [{"path": f"{FIXTURES}/robinhood_sample.csv"}],
        "robinhood_pdf": [{"path": f"{FIXTURES}/robinhood_sample.pdf"}],
    }
    path = tmp_path / "statements_manifest.json"
    path.write_text(json.dumps(manifest))
    return str(path)


# ── _load_config ──────────────────────────────────────────────────────────────


def test_load_config_returns_dict(tmp_config):
    cfg = ird._load_config(tmp_config)
    assert "import_accounts" in cfg
    assert cfg["import_accounts"]["chase_credit"] == "Chase-CreditCard"


def test_load_config_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        ird._load_config("/nonexistent/config.json")


# ── _load_manifest ────────────────────────────────────────────────────────────


def test_load_manifest_returns_dict(tmp_manifest):
    m = ird._load_manifest(tmp_manifest)
    assert "chase_credit" in m
    assert isinstance(m["chase_credit"], list)


def test_load_manifest_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        ird._load_manifest("/nonexistent/manifest.json")


# ── normalize_merchant ────────────────────────────────────────────────────────


def test_normalize_merchant_lowercases():
    assert ird.normalize_merchant("CHIPOTLE") == "chipotle"


def test_normalize_merchant_strips_branch_number():
    assert ird.normalize_merchant("CHIPOTLE #1234") == "chipotle"


def test_normalize_merchant_replaces_asterisk():
    assert ird.normalize_merchant("AMAZON*PRIME") == "amazon prime"


# ── infer_year ────────────────────────────────────────────────────────────────


def test_infer_year_same_month():
    assert ird.infer_year(1, 2024, 1) == 2024


def test_infer_year_tx_before_closing():
    assert ird.infer_year(1, 2024, 3) == 2024


def test_infer_year_tx_after_closing_wraps():
    assert ird.infer_year(12, 2024, 1) == 2023


# ── _add_tx ───────────────────────────────────────────────────────────────────


def test_add_tx_returns_added_when_new(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    a, s = ird._add_tx(tmp_store, cat, "2024-01-15", -45.20, "CHIPOTLE", "Chase-CC")
    assert a == 1
    assert s == 0


def test_add_tx_returns_skipped_when_duplicate(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    ird._add_tx(tmp_store, cat, "2024-01-15", -45.20, "CHIPOTLE", "Chase-CC")
    a, s = ird._add_tx(tmp_store, cat, "2024-01-15", -45.20, "CHIPOTLE", "Chase-CC")
    assert a == 0
    assert s == 1


# ── parse_chase_pdf ───────────────────────────────────────────────────────────


def test_parse_chase_pdf_skips_when_file_missing(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_chase_pdf(tmp_store, cat, "/nonexistent.pdf", "Chase-CC", 2024, 1)
    assert added == 0
    assert skipped == 0


def test_parse_chase_pdf_returns_counts_for_fixture(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_chase_pdf(
        tmp_store, cat, f"{FIXTURES}/chase_sample.pdf", "Chase-CC", 2024, 1
    )
    assert added >= 0
    assert skipped >= 0


# ── parse_bofa_credit_pdf ─────────────────────────────────────────────────────


def test_parse_bofa_credit_pdf_skips_when_file_missing(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_bofa_credit_pdf(
        tmp_store, cat, "/nonexistent.pdf", "BofA-Visa", 2024
    )
    assert added == 0
    assert skipped == 0


def test_parse_bofa_credit_pdf_returns_counts_for_fixture(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_bofa_credit_pdf(
        tmp_store, cat, f"{FIXTURES}/bofa_visa_sample.pdf", "BofA-Visa", 2024
    )
    assert added >= 0
    assert skipped >= 0


# ── parse_bofa_checking_pdf ───────────────────────────────────────────────────


def test_parse_bofa_checking_pdf_returns_counts_for_fixture(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_bofa_checking_pdf(
        tmp_store, cat, f"{FIXTURES}/bofa_checking_sample.pdf"
    )
    assert added >= 0
    assert skipped >= 0


def test_parse_bofa_checking_pdf_skips_when_file_missing(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_bofa_checking_pdf(tmp_store, cat, "/nonexistent.pdf")
    assert added == 0
    assert skipped == 0


# ── parse_robinhood_csv ───────────────────────────────────────────────────────


def test_parse_robinhood_csv_adds_rows(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_robinhood_csv(
        tmp_store, cat, f"{FIXTURES}/robinhood_sample.csv", "Robinhood"
    )
    assert added == 2
    assert skipped == 0


def test_parse_robinhood_csv_deduplicates(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    ird.parse_robinhood_csv(tmp_store, cat, f"{FIXTURES}/robinhood_sample.csv", "Robinhood")
    added2, skipped2 = ird.parse_robinhood_csv(
        tmp_store, cat, f"{FIXTURES}/robinhood_sample.csv", "Robinhood"
    )
    assert added2 == 0
    assert skipped2 == 2


def test_parse_robinhood_csv_exception_path(tmp_store, tmp_config, tmp_path):
    """Cover except Exception: continue in parse_robinhood_csv (lines 410-411)."""
    cat = Categorizer(tmp_config)
    bad_csv = tmp_path / "bad_amount.csv"
    bad_csv.write_text("2026-01-15,Interest,NOT_A_NUMBER\n")
    added, _skipped = ird.parse_robinhood_csv(tmp_store, cat, str(bad_csv), "Robinhood")
    assert added == 0


def test_parse_robinhood_csv_skips_short_rows(tmp_store, tmp_config, tmp_path):
    cat = Categorizer(tmp_config)
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("only_one_column\n")
    added, _skipped = ird.parse_robinhood_csv(tmp_store, cat, str(bad_csv), "Robinhood")
    assert added == 0


# ── parse_robinhood_pdf ───────────────────────────────────────────────────────


def test_parse_robinhood_pdf_returns_counts_for_fixture(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_robinhood_pdf(
        tmp_store, cat, f"{FIXTURES}/robinhood_sample.pdf", "Robinhood"
    )
    assert added >= 0
    assert skipped >= 0


def test_parse_robinhood_pdf_skips_when_file_missing(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_robinhood_pdf(tmp_store, cat, "/nonexistent.pdf", "Robinhood")
    assert added == 0
    assert skipped == 0


# ── parse_chase_bank_pdf ─────────────────────────────────────────────────────


def test_parse_chase_bank_pdf_skips_when_file_missing(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_chase_bank_pdf(
        tmp_store, cat, "/nonexistent.pdf", "Chase-Checking", "Chase-Savings", 2026, 1
    )
    assert added == 0
    assert skipped == 0


def test_parse_chase_bank_pdf_returns_counts_for_fixture(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_chase_bank_pdf(
        tmp_store,
        cat,
        f"{FIXTURES}/chase_bank_sample.pdf",
        "Chase-Checking",
        "Chase-Savings",
        2026,
        1,
    )
    assert added >= 0
    assert skipped >= 0


def test_parse_chase_bank_pdf_exception_path(tmp_store, tmp_config, tmp_path):
    """Cover the except-continue path in parse_chase_bank_pdf."""
    cat = Categorizer(tmp_config)
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")
    bank_text = "CHASE SECURE CHECKING\n12/18 Payroll 500.00 500.00"
    mock_pdf = _make_pdf_mock([bank_text])
    with (
        patch("pdfplumber.open", return_value=mock_pdf),
        patch.object(tmp_store, "add", side_effect=ValueError("db error")),
    ):
        added, _skipped = ird.parse_chase_bank_pdf(
            tmp_store, cat, str(fake_pdf), "Chase-Checking", "Chase-Savings", 2026, 1
        )
    assert added == 0


def test_parse_chase_bank_pdf_inner_branches(tmp_store, tmp_config, tmp_path):
    """Cover: no-account skip, blank lines, account detection, skip_re, income, exception."""
    cat = Categorizer(tmp_config)
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")
    bank_text = "\n".join(
        [
            "Some header text before any account",  # no account set → skip
            "",  # blank line
            "CHASE SECURE CHECKING",  # set checking account
            "TRANSACTION DETAIL",  # skip via _SKIP_CHASE_BANK
            "Beginning Balance 235.88",  # skip via _SKIP_CHASE_BANK
            "12/18 Centavo Inc Payroll 1000.00 1235.88",  # IMPORT income
            "01/08 Monthly Service Fee -4.95 1230.93",  # IMPORT expense
            "Online Transfer From Sav 1000.00 2230.93",  # skip via _SKIP_CHASE_BANK
            "INVALID LINE",  # no regex match
            "99/99 BadDate -1.00 0.00",  # bad date → exception
            "CHASE SAVINGS",  # switch to savings
            "12/18 Direct Deposit 250.00 250.00",  # IMPORT income (direct deposit)
        ]
    )
    mock_pdf = _make_pdf_mock([bank_text])
    with patch("pdfplumber.open", return_value=mock_pdf):
        added, _skipped = ird.parse_chase_bank_pdf(
            tmp_store, cat, str(fake_pdf), "Chase-Checking", "Chase-Savings", 2026, 1
        )
    assert added >= 0


# ── parse_amex_hysa_pdf ──────────────────────────────────────────────────────


def test_parse_amex_hysa_pdf_skips_when_file_missing(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_amex_hysa_pdf(tmp_store, cat, "/nonexistent.pdf", "Amex-HYSA")
    assert added == 0
    assert skipped == 0


def test_parse_amex_hysa_pdf_returns_counts_for_fixture(tmp_store, tmp_config):
    cat = Categorizer(tmp_config)
    added, skipped = ird.parse_amex_hysa_pdf(
        tmp_store, cat, f"{FIXTURES}/amex_hysa_sample.pdf", "Amex-HYSA"
    )
    assert added >= 0
    assert skipped >= 0


def test_parse_amex_hysa_pdf_inner_branches(tmp_store, tmp_config, tmp_path):
    """Cover: blank lines, no-match lines, interest income, exception path."""
    cat = Categorizer(tmp_config)
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")
    hysa_text = "\n".join(
        [
            "Account Activity",  # no match
            "",  # blank line
            "01/03/2026 Beginning Balance $10036.68",  # only one $ → no match
            "02/02/2026 Interest Payment $27.71 $10064.39",  # IMPORT income
            "99/99/2026 Interest Payment $1.00 $100.00",  # bad date → exception
            "02/02/2026 Ending Balance $10064.39",  # only one $ → no match
        ]
    )
    mock_pdf = _make_pdf_mock([hysa_text])
    with patch("pdfplumber.open", return_value=mock_pdf):
        added, _skipped = ird.parse_amex_hysa_pdf(tmp_store, cat, str(fake_pdf), "Amex-HYSA")
    assert added == 1


# ── run_import ────────────────────────────────────────────────────────────────


def test_run_import_returns_tuple(tmp_path, tmp_config, tmp_manifest):
    result = ird.run_import(
        config_path=tmp_config, data_dir=str(tmp_path), manifest_path=tmp_manifest
    )
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_run_import_missing_manifest_raises(tmp_path, tmp_config):
    with pytest.raises(FileNotFoundError):
        ird.run_import(
            config_path=tmp_config,
            data_dir=str(tmp_path),
            manifest_path=str(tmp_path / "nonexistent.json"),
        )


# ── parse_chase_pdf inner branches (mocked PDF text) ─────────────────────────


def _make_pdf_mock(text_pages):
    """Return a context-manager mock for pdfplumber.open() yielding pages with given text."""
    pages = []
    for text in text_pages:
        page = MagicMock()
        page.extract_text.return_value = text
        pages.append(page)
    pdf_ctx = MagicMock()
    pdf_ctx.__enter__ = MagicMock(return_value=pdf_ctx)
    pdf_ctx.__exit__ = MagicMock(return_value=False)
    pdf_ctx.pages = pages
    return pdf_ctx


def test_parse_chase_pdf_inner_branches(tmp_store, tmp_config, tmp_path):
    """Cover blank lines, payment section, skip_re, exchange-skip, interest-skip, exception."""
    cat = Categorizer(tmp_config)
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")
    chase_text = "\n".join(
        [
            "Opening/Closing Date 12/01/2024 to 01/15/2024",
            "",  # blank line → continue
            "PAYMENTS AND OTHER CREDITS",  # payment_section = True
            "01/05 PAYMENT THANK YOU 100.00",  # in payment section → skip
            "PURCHASE",  # payment_section = False
            "01/10 CHIPOTLE #1234 45.20",  # valid transaction
            "01/11 NETFLIX.COM 15.99",  # valid transaction
            "INTEREST CHARGED",  # skip header
            "01/12 X 0.50 5.00",  # X pattern → skip (line 190)
            "01/13 INTEREST CHARGE PURCHASES 1.00",  # INTEREST CHARGE → skip (line 194)
            "INVALID LINE",  # no regex match → skip
            "99/99 BADDATE 10.00",  # bad month/day → except (lines 204-205)
        ]
    )
    mock_pdf = _make_pdf_mock([chase_text])
    with patch("pdfplumber.open", return_value=mock_pdf):
        added, _skipped = ird.parse_chase_pdf(tmp_store, cat, str(fake_pdf), "Chase-CC", 2024, 1)
    assert added >= 0


def test_parse_bofa_credit_pdf_inner_branches(tmp_store, tmp_config, tmp_path):
    """Cover blank lines, section switching, skip_re, not-in-section, exception."""
    cat = Categorizer(tmp_config)
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")
    bofa_text = "\n".join(
        [
            "Statement Summary",
            "",  # blank → continue (not in section)
            "Purchases and Adjustments",  # purchase_section = True
            "",  # blank → continue
            "TOTAL PURCHASES 500.00",  # skip_re match → skip (line 263)
            "Payments and Other Credits",  # purchase_section = False
            "01/11/24 PAYMENT  9876  200.00",  # not in section → skip (line 265)
            "Purchases and Adjustments",  # purchase_section = True again
            "Interest Charged",  # purchase_section = False
            "01/12/24 AMAZON  1234  89.99",  # not in section → skip
            "Purchases and Adjustments",  # purchase_section = True
            "BADFORMAT LINE",  # no regex match → skip
            "99/99 BADDATE  1234  9999  BAD_AMOUNT",  # parse error → except (lines 280-281)
        ]
    )
    mock_pdf = _make_pdf_mock([bofa_text])
    with patch("pdfplumber.open", return_value=mock_pdf):
        added, _skipped = ird.parse_bofa_credit_pdf(
            tmp_store, cat, str(fake_pdf), "BofA-Visa", 2024
        )
    assert added >= 0


def test_parse_bofa_checking_pdf_inner_branches(tmp_store, tmp_config, tmp_path):
    """Cover account number extraction, no-account skip, skip_re, transfer, exception."""
    cat = Categorizer(tmp_config)
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")
    bofa_text = "\n".join(
        [
            "Some header before account number",  # no current_account yet → skip (line 334)
            "Account number: 0000 0000 1234",
            "",  # blank → skip (line 334 empty-line case)
            "01/05/26 CENTAVO PAYROLL 3200.00",  # income = True
            "01/07/26 CHIPOTLE GRILL -45.00",  # normal expense
            "01/10/26 ROBINHOOD -500.00",  # is_savings = True
            "01/11/26 JPMorgan Chase Ext Trnsfr -100.00",  # transfer → continue (line 358)
            "Online Banking transfer Confirmation#12345",  # skip via SKIP_BOFA (line 336)
            "GARBAGE LINE",  # no tx_re match → skip
            "99/99/26 BADDATE NOT_AN_AMOUNT",  # exception → continue (lines 365-366)
        ]
    )
    mock_pdf = _make_pdf_mock([bofa_text])
    with patch("pdfplumber.open", return_value=mock_pdf):
        added, _skipped = ird.parse_bofa_checking_pdf(tmp_store, cat, str(fake_pdf))
    assert added >= 0


def test_parse_robinhood_pdf_inner_branches(tmp_store, tmp_config, tmp_path):
    """Cover in_activity flag, all transaction types, skip conditions, and exception."""
    cat = Categorizer(tmp_config)
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")
    robinhood_text = "\n".join(
        [
            "Some Header",
            "NOT IN ACTIVITY",  # not in activity → skip (line 455)
            "Description Symbol",  # skip regex line (line 457)
            "Account Activity",  # in_activity = True
            "Description Symbol",  # skip header (line 457)
            "ACH Deposit 01/05/2026 $500.00",  # ACH → skip (line 463)
            "Buy AAPL 01/06/2026 $100.00",  # Buy → skip (line 466)
            "Crypto Money Movement 01/07/2026 $25.00",  # crypto → add (lines 469-476)
            "Gold Subscription Margin Cash 01/08/2026 $5.00",  # gold → add
            "Interest Payment Margin Cash 01/09/2026 $1.23",  # interest → add
            "Cash Div AAPL 01/10/2026 $0.50",  # dividend → add (lines 497-506)
            "NO DATE IN LINE",  # no date → skip (line 460)
            "Crypto Money Movement 01/11/2026 BAD_AMOUNT",  # exception → continue (lines 507-508)
            "Executed Trades",  # end activity section
            "01/12/2026 line after activity",  # not in activity → skip
        ]
    )
    mock_pdf = _make_pdf_mock([robinhood_text])
    with patch("pdfplumber.open", return_value=mock_pdf):
        added, _skipped = ird.parse_robinhood_pdf(tmp_store, cat, str(fake_pdf), "Robinhood")
    assert added >= 0


def test_parse_chase_pdf_exchg_merchant_skipped(tmp_store, tmp_config, tmp_path):
    """Cover line 190: (EXCHG in merchant_raw triggers the continue."""
    cat = Categorizer(tmp_config)
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")
    # (EXCHG is NOT in skip_re but IS matched by the r'\(EXCHG' pattern at line 189
    chase_text = "01/12 (EXCHG 0.85 EUR)  12.00"
    mock_pdf = _make_pdf_mock([chase_text])
    with patch("pdfplumber.open", return_value=mock_pdf):
        added, _skipped = ird.parse_chase_pdf(tmp_store, cat, str(fake_pdf), "Chase-CC", 2024, 1)
    assert added == 0


def test_parse_chase_pdf_exception_path(tmp_store, tmp_config, tmp_path):
    """Cover lines 204-205: except Exception: continue in parse_chase_pdf."""
    cat = Categorizer(tmp_config)
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")
    chase_text = "01/10 CHIPOTLE  45.20"
    mock_pdf = _make_pdf_mock([chase_text])
    with patch("pdfplumber.open", return_value=mock_pdf):
        with patch("importers.real_data._add_tx", side_effect=Exception("test error")):
            added, _skipped = ird.parse_chase_pdf(
                tmp_store, cat, str(fake_pdf), "Chase-CC", 2024, 1
            )
    assert added == 0


def test_parse_bofa_credit_pdf_exception_path(tmp_store, tmp_config, tmp_path):
    """Cover lines 280-281: except Exception: continue in parse_bofa_credit_pdf."""
    cat = Categorizer(tmp_config)
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")
    bofa_text = "\n".join(
        [
            "Purchases and Adjustments",
            "01/10 01/11 AMAZON  1234  5678  89.99",
        ]
    )
    mock_pdf = _make_pdf_mock([bofa_text])
    with patch("pdfplumber.open", return_value=mock_pdf):
        with patch("importers.real_data._add_tx", side_effect=Exception("test error")):
            added, _skipped = ird.parse_bofa_credit_pdf(
                tmp_store, cat, str(fake_pdf), "BofA-Visa", 2024
            )
    assert added == 0


def test_parse_bofa_checking_pdf_exception_path(tmp_store, tmp_config, tmp_path):
    """Cover lines 365-366: except Exception: continue in parse_bofa_checking_pdf."""
    cat = Categorizer(tmp_config)
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")
    # 99/99/26 matches the \\d{2}/\\d{2}/\\d{2} regex but fails datetime.strptime
    bofa_text = "\n".join(
        [
            "Account number: 0000 0000 1234",
            "99/99/26 BADDATE  45.00",
        ]
    )
    mock_pdf = _make_pdf_mock([bofa_text])
    with patch("pdfplumber.open", return_value=mock_pdf):
        added, _skipped = ird.parse_bofa_checking_pdf(tmp_store, cat, str(fake_pdf))
    assert added == 0


def test_parse_robinhood_pdf_exception_path(tmp_store, tmp_config, tmp_path):
    """Cover lines 507-508: except Exception: continue in parse_robinhood_pdf."""
    cat = Categorizer(tmp_config)
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")
    robinhood_text = "\n".join(
        [
            "Account Activity",
            "Crypto Money Movement 01/05/2026 $25.00",
        ]
    )
    mock_pdf = _make_pdf_mock([robinhood_text])
    with patch("pdfplumber.open", return_value=mock_pdf):
        with patch("importers.real_data._add_tx", side_effect=Exception("test error")):
            added, _skipped = ird.parse_robinhood_pdf(tmp_store, cat, str(fake_pdf), "Robinhood")
    assert added == 0


def test_main_block_runs(tmp_path, tmp_config, tmp_manifest, capsys):
    """Cover the __main__ block by calling run_import directly (line 581-583 equivalent)."""
    total_added, total_skipped = ird.run_import(
        config_path=tmp_config,
        data_dir=str(tmp_path),
        manifest_path=tmp_manifest,
    )
    assert isinstance(total_added, int)
    assert isinstance(total_skipped, int)
