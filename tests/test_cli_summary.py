import pytest
import os
from click.testing import CliRunner
from main import cli

@pytest.fixture
def runner_with_data(tmp_path):
    runner = CliRunner()
    # Seed with known transactions
    txs = [
        ["--amount", "-45.20", "--merchant", "Chipotle", "--account", "Chase-Checking", "--data-dir", str(tmp_path)],
        ["--amount", "-15.99", "--merchant", "Netflix", "--account", "Chase-Checking", "--data-dir", str(tmp_path)],
        ["--amount", "2500.00", "--merchant", "Payroll", "--account", "Chase-Checking", "--income", "--data-dir", str(tmp_path)],
    ]
    for args in txs:
        runner.invoke(cli, ["add"] + args)
    return runner, tmp_path

def test_summary_shows_income_and_expenses(runner_with_data):
    runner, tmp_path = runner_with_data
    result = runner.invoke(cli, ["summary", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "2500" in result.output
    assert "61" in result.output  # 45.20 + 15.99

def test_networth_command_runs(runner_with_data):
    runner, tmp_path = runner_with_data
    # Create accounts.json
    import json
    accounts = {"accounts": [{"name": "Chase-Checking", "type": "checking", "institution": "Chase",
                               "balance": 4200.00, "currency": "USD", "last_updated": "2024-01-15"}]}
    (tmp_path / "accounts.json").write_text(json.dumps(accounts))
    result = runner.invoke(cli, ["networth", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "4200" in result.output

def test_spending_command_filters_by_category(runner_with_data):
    runner, tmp_path = runner_with_data
    result = runner.invoke(cli, ["spending", "--category", "Food & Dining", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Chipotle" in result.output or "chipotle" in result.output

def test_tag_income_command(runner_with_data):
    runner, tmp_path = runner_with_data
    import pandas as pd
    df = pd.read_csv(tmp_path / "transactions.csv")
    tx_id = df.iloc[0]["id"]
    result = runner.invoke(cli, ["tag", tx_id, "--income", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    df2 = pd.read_csv(tmp_path / "transactions.csv")
    row = df2[df2["id"] == tx_id].iloc[0]
    assert str(row["is_income"]).lower() == "true"


def test_summary_empty_shows_no_transactions(tmp_path):
    """Cover summary empty-df path (finance.py lines 129-130)."""
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cli, ["summary", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "No transactions" in result.output


def test_top_categories_command(runner_with_data):
    """Cover top_categories command body (finance.py lines 152-167)."""
    runner, tmp_path = runner_with_data
    result = runner.invoke(cli, ["top-categories", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0


def test_top_categories_empty(tmp_path):
    """Cover top_categories empty-df path."""
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cli, ["top-categories", "--data-dir", str(tmp_path)])
    assert "No transactions" in result.output


def test_spending_empty_df(tmp_path):
    """Cover spending empty-df path (finance.py lines 180-181)."""
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cli, ["spending", "--category", "Food & Dining", "--data-dir", str(tmp_path)])
    assert "No transactions" in result.output


def test_spending_with_year_filter(runner_with_data):
    """Cover the year filter branch in spending (finance.py line 185)."""
    runner, tmp_path = runner_with_data
    import datetime
    year = str(datetime.date.today().year)
    result = runner.invoke(cli, ["spending", "--category", "Food & Dining", "--year", year, "--data-dir", str(tmp_path)])
    assert result.exit_code == 0


def test_spending_no_category_match(runner_with_data):
    """Cover spending empty-subset path (finance.py lines 188-189)."""
    runner, tmp_path = runner_with_data
    result = runner.invoke(cli, ["spending", "--category", "NonExistentCategory", "--data-dir", str(tmp_path)])
    assert "No transactions found for category" in result.output


def test_networth_missing_accounts_json(tmp_path):
    """Cover networth missing-accounts path (finance.py lines 208-209)."""
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cli, ["networth", "--data-dir", str(tmp_path)])
    assert "No accounts.json" in result.output


def test_account_update_creates_and_updates(tmp_path):
    """Cover account_update command body including existing-account update path (lines 238-254)."""
    from click.testing import CliRunner
    runner = CliRunner()
    # First call creates the account
    result = runner.invoke(cli, [
        "account", "update", "BofA-Checking",
        "--balance", "5000.00", "--type", "checking",
        "--data-dir", str(tmp_path)
    ])
    assert result.exit_code == 0
    assert "Updated" in result.output
    # Second call updates existing account (line 246-248)
    result2 = runner.invoke(cli, [
        "account", "update", "BofA-Checking",
        "--balance", "6000.00",
        "--data-dir", str(tmp_path)
    ])
    assert result2.exit_code == 0


def test_tag_without_flag_shows_message(runner_with_data):
    """Cover tag command with no --income or --savings (finance.py lines 271-273)."""
    runner, tmp_path = runner_with_data
    result = runner.invoke(cli, ["tag", "aabbccddeeff0011", "--data-dir", str(tmp_path)])
    assert "Specify" in result.output or result.exit_code == 0


def test_goal_set_monthly_missing_amount(tmp_path):
    """Cover goal set monthly without --amount (finance.py lines 293-295)."""
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cli, ["goal", "set", "monthly", "--data-dir", str(tmp_path)])
    assert "--amount required" in result.output


def test_goal_set_named_missing_target(tmp_path):
    """Cover goal set named without --target/--by (finance.py lines 299-301)."""
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cli, ["goal", "set", "Emergency Fund", "--data-dir", str(tmp_path)])
    assert "--target and --by required" in result.output


def test_goal_status_with_goals(tmp_path):
    """Cover goal status table output with named goals (finance.py lines 315-327)."""
    from click.testing import CliRunner
    import json
    runner = CliRunner()
    goals = {
        "monthly_target": 500.0,
        "goals": [{"name": "Emergency Fund", "target_amount": 10000.0,
                   "current_amount": 2500.0, "deadline": "2026-12", "created": "2026-01-01"}],
        "monthly_streak": {"current": 2, "best": 4}
    }
    (tmp_path / "goals.json").write_text(json.dumps(goals))
    result = runner.invoke(cli, ["goal", "status", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Emergency Fund" in result.output


def test_tag_savings_command(runner_with_data):
    """Cover tag --savings path (finance.py line 270)."""
    runner, tmp_path = runner_with_data
    import pandas as pd
    df = pd.read_csv(tmp_path / "transactions.csv")
    tx_id = df.iloc[0]["id"]
    result = runner.invoke(cli, ["tag", tx_id, "--savings", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    df2 = pd.read_csv(tmp_path / "transactions.csv")
    row = df2[df2["id"] == tx_id].iloc[0]
    assert str(row["is_savings"]).lower() == "true"


def test_goal_status_no_named_goals(tmp_path):
    """Cover goal status empty-goals path (finance.py lines 315-316)."""
    import json
    from click.testing import CliRunner
    runner = CliRunner()
    goals = {"monthly_target": 500.0, "goals": [], "monthly_streak": {"current": 0, "best": 0}}
    (tmp_path / "goals.json").write_text(json.dumps(goals))
    result = runner.invoke(cli, ["goal", "status", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "No named goals" in result.output


def test_cards_command_no_cards_file(tmp_path):
    """Shows empty state message when data/cards.json does not exist."""
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cli, ["cards", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "No cards configured" in result.output


def test_cards_command_with_cards(runner_with_data):
    """Shows portfolio table when cards.json is present."""
    import json
    runner, tmp_path = runner_with_data
    cards = {
        "cards": [{
            "name": "Chase Sapphire Preferred",
            "issuer": "Chase",
            "annual_fee": 95,
            "reward_type": "points",
            "points_cpp": 0.0125,
            "rewards": {"Food & Dining": 3.0, "Transport": 2.0,
                        "Subscriptions": 1.0, "Other": 1.0},
        }]
    }
    (tmp_path / "cards.json").write_text(json.dumps(cards))
    result = runner.invoke(cli, ["cards", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Chase Sapphire Preferred" in result.output


def test_cards_command_shows_optimization(tmp_path):
    """Cover missed_rewards >= 5 and top-optimizer output (main.py lines 382, 390-396)."""
    import json
    from click.testing import CliRunner
    runner = CliRunner()
    # Seed large transactions so annualised spend is meaningful
    for args in [
        ["add", "--amount", "-500.00", "--merchant", "Chipotle",
         "--account", "Chase", "--data-dir", str(tmp_path)],
        ["add", "--amount", "-200.00", "--merchant", "Netflix",
         "--account", "Chase", "--data-dir", str(tmp_path)],
    ]:
        runner.invoke(cli, args)
    cards = {
        "cards": [
            {
                "name": "Chase Sapphire Preferred",
                "issuer": "Chase", "annual_fee": 95, "reward_type": "points",
                "points_cpp": 0.0125,
                "rewards": {"Food & Dining": 3.0, "Subscriptions": 1.0, "Other": 1.0},
            },
            {
                "name": "BofA Travel",
                "issuer": "BofA", "annual_fee": 95, "reward_type": "points",
                "points_cpp": 0.01,
                "rewards": {"Food & Dining": 1.5, "Subscriptions": 3.0, "Other": 1.5},
            },
        ]
    }
    (tmp_path / "cards.json").write_text(json.dumps(cards))
    result = runner.invoke(cli, ["cards", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    # missed_rewards >= 5 → callout shown; top_opts → optimizer table shown
    assert "leaving" in result.output or "Category Optimizer" in result.output


def test_dashboard_opens_browser(runner_with_data, tmp_path):
    """Cover the webbrowser.open path in dashboard command (finance.py line 341)."""
    from unittest.mock import patch
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "report.html")
    with patch("webbrowser.open") as mock_open:
        result = runner.invoke(cli, [
            "dashboard", "--output", out_path, "--data-dir", str(data_dir)
        ])
    assert result.exit_code == 0
    mock_open.assert_called_once()
