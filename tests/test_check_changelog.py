"""Tests for scripts/check_changelog.py changelog reminder logic."""
import sys
import os
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from check_changelog import is_nontrivial_file, changelog_is_staged, should_warn, get_staged_files, main


def test_py_file_is_nontrivial():
    assert is_nontrivial_file("main.py") is True


def test_html_file_is_nontrivial():
    assert is_nontrivial_file("templates/dashboard.html.j2") is True


def test_config_json_is_nontrivial():
    assert is_nontrivial_file("config.json") is True


def test_txt_file_is_trivial():
    assert is_nontrivial_file("notes.txt") is False


def test_md_file_is_trivial():
    assert is_nontrivial_file("README.md") is False


def test_changelog_staged_when_in_list():
    assert changelog_is_staged(["CHANGELOG.md", "finance.py"]) is True


def test_changelog_not_staged_when_absent():
    assert changelog_is_staged(["finance.py", "data_store.py"]) is False


def test_should_warn_when_nontrivial_staged_and_changelog_absent():
    assert should_warn(["finance.py"], changelog_staged=False) is True


def test_should_not_warn_when_changelog_staged():
    assert should_warn(["finance.py"], changelog_staged=True) is False


def test_should_not_warn_when_only_trivial_files():
    assert should_warn(["README.md"], changelog_staged=False) is False


def test_should_not_warn_when_no_files():
    assert should_warn([], changelog_staged=False) is False


def test_get_staged_files_returns_list():
    mock_result = MagicMock()
    mock_result.stdout = "finance.py\nconfig.json\n"
    with patch("subprocess.run", return_value=mock_result):
        files = get_staged_files()
    assert files == ["finance.py", "config.json"]


def test_get_staged_files_empty():
    mock_result = MagicMock()
    mock_result.stdout = "  \n"
    with patch("subprocess.run", return_value=mock_result):
        files = get_staged_files()
    assert files == []


def test_main_no_warning_when_changelog_staged(capsys):
    mock_result = MagicMock()
    mock_result.stdout = "CHANGELOG.md\nfinance.py\n"
    with patch("subprocess.run", return_value=mock_result):
        result = main()
    assert result == 0
    assert capsys.readouterr().out == ""


def test_main_prints_warning_when_py_staged_without_changelog(capsys):
    mock_result = MagicMock()
    mock_result.stdout = "finance.py\n"
    with patch("subprocess.run", return_value=mock_result):
        result = main()
    assert result == 0
    assert "WARNING" in capsys.readouterr().out


def test_main_no_warning_for_only_trivial_files(capsys):
    mock_result = MagicMock()
    mock_result.stdout = "README.md\n"
    with patch("subprocess.run", return_value=mock_result):
        result = main()
    assert result == 0
    assert capsys.readouterr().out == ""
