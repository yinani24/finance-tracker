"""Tests for scripts/check_secrets.py secret detection logic."""
import sys
import os
import subprocess
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from check_secrets import (
    contains_card_pattern,
    contains_statements_path,
    contains_data_file,
    check_content,
    get_staged_files,
    scan_staged_files,
    main,
)


def test_card_pattern_detects_four_digit_groups():
    assert contains_card_pattern("account Chase-CreditCard-1234") is True


def test_card_pattern_no_false_positive_on_clean_text():
    assert contains_card_pattern("Chase-CreditCard normal text") is False


def test_card_pattern_detects_16_digit_string():
    assert contains_card_pattern("card number 1234567890123456") is True


def test_statements_path_detects_statements_dir():
    assert contains_statements_path("statements/myfile.pdf") is True


def test_statements_path_clean():
    assert contains_statements_path("data/transactions.csv") is False


def test_data_file_detects_transactions():
    assert contains_data_file("data/transactions.csv") is True


def test_data_file_detects_accounts():
    assert contains_data_file("data/accounts.json") is True


def test_data_file_detects_goals():
    assert contains_data_file("data/goals.json") is True


def test_data_file_clean():
    assert contains_data_file("data/other.txt") is False


def test_check_content_returns_violations_list():
    violations = check_content("Chase-CreditCard-1234", "test.py")
    assert len(violations) > 0
    assert "test.py" in violations[0]


def test_check_content_clean_returns_empty():
    violations = check_content("normal code here", "test.py")
    assert violations == []


def test_check_content_statements_path_violation():
    violations = check_content('path = "statements/file.pdf"', "config.py")
    assert len(violations) == 1
    assert "statements/" in violations[0]


def test_get_staged_files_returns_list():
    mock_result = MagicMock()
    mock_result.stdout = "finance.py\ndata_store.py\n"
    with patch("subprocess.run", return_value=mock_result):
        files = get_staged_files()
    assert files == ["finance.py", "data_store.py"]


def test_get_staged_files_empty():
    mock_result = MagicMock()
    mock_result.stdout = ""
    with patch("subprocess.run", return_value=mock_result):
        files = get_staged_files()
    assert files == []


def test_scan_staged_files_clean(tmp_path):
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("x = 1\n")
    mock_result = MagicMock()
    mock_result.stdout = str(clean_file) + "\n"
    with patch("subprocess.run", return_value=mock_result):
        violations = scan_staged_files()
    assert violations == []


def test_scan_staged_files_data_file_blocked():
    mock_result = MagicMock()
    mock_result.stdout = "data/transactions.csv\n"
    with patch("subprocess.run", return_value=mock_result):
        violations = scan_staged_files()
    assert len(violations) == 1
    assert "sensitive data file" in violations[0]


def test_scan_staged_files_card_number_blocked(tmp_path):
    bad_file = tmp_path / "config.py"
    bad_file.write_text('account = "1234-5678-9012-3456"\n')
    mock_result = MagicMock()
    mock_result.stdout = str(bad_file) + "\n"
    with patch("subprocess.run", return_value=mock_result):
        violations = scan_staged_files()
    assert len(violations) == 1


def test_scan_staged_files_skips_unreadable_file():
    mock_result = MagicMock()
    mock_result.stdout = "/nonexistent/path/to/file.py\n"
    with patch("subprocess.run", return_value=mock_result):
        violations = scan_staged_files()
    assert violations == []


def test_main_no_violations():
    with patch("check_secrets.scan_staged_files", return_value=[]):
        assert main() == 0


def test_main_with_violations(capsys):
    violations = ["  bad.py: contains card-number-like digit pattern"]
    with patch("check_secrets.scan_staged_files", return_value=violations):
        result = main()
    assert result == 1
    captured = capsys.readouterr()
    assert "COMMIT BLOCKED" in captured.out
