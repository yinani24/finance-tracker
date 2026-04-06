import pytest
from click.testing import CliRunner

from main import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_import_csv_command_succeeds(runner, tmp_path):
    # Copy fixture to tmp dir
    csv_path = "tests/fixtures/chase_sample.csv"
    result = runner.invoke(
        cli,
        [
            "import",
            "csv",
            csv_path,
            "--account",
            "Chase-Checking",
            "--bank",
            "chase",
            "--data-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Imported" in result.output


def test_import_csv_skips_duplicates(runner, tmp_path):
    csv_path = "tests/fixtures/chase_sample.csv"
    runner.invoke(
        cli,
        [
            "import",
            "csv",
            csv_path,
            "--account",
            "Chase-Checking",
            "--bank",
            "chase",
            "--data-dir",
            str(tmp_path),
        ],
    )
    result = runner.invoke(
        cli,
        [
            "import",
            "csv",
            csv_path,
            "--account",
            "Chase-Checking",
            "--bank",
            "chase",
            "--data-dir",
            str(tmp_path),
        ],
    )
    # All 3 transactions are duplicates — should import 0 new
    assert "0 new" in result.output


def test_add_manual_transaction(runner, tmp_path):
    result = runner.invoke(
        cli,
        [
            "add",
            "--amount",
            "-45.20",
            "--merchant",
            "Chipotle",
            "--account",
            "Chase-Checking",
            "--data-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Added" in result.output


def test_import_pdf_command_succeeds(runner, tmp_path):
    """Cover the import_pdf command body (finance.py lines 78-82)."""
    result = runner.invoke(
        cli,
        [
            "import",
            "pdf",
            "tests/fixtures/chase_sample.pdf",
            "--account",
            "Chase-Checking",
            "--bank",
            "chase",
            "--data-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Imported" in result.output


def test_add_duplicate_shows_skipped_message(runner, tmp_path):
    """Cover the duplicate path in add command (finance.py line 114)."""
    args = [
        "add",
        "--amount",
        "-20.00",
        "--merchant",
        "Starbucks",
        "--account",
        "Chase-Checking",
        "--data-dir",
        str(tmp_path),
    ]
    runner.invoke(cli, args)
    result = runner.invoke(cli, args)  # second invoke → duplicate
    assert "already exists" in result.output or "skipped" in result.output.lower()
