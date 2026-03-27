import pytest
import os
from click.testing import CliRunner
from main import cli

@pytest.fixture
def runner_with_data(tmp_path):
    runner = CliRunner()
    txs = [
        ["--amount", "-45.20", "--merchant", "Chipotle", "--account", "Chase-Checking", "--data-dir", str(tmp_path)],
        ["--amount", "-15.99", "--merchant", "Netflix", "--account", "Chase-Checking", "--data-dir", str(tmp_path)],
        ["--amount", "2500.00", "--merchant", "Payroll", "--account", "Chase-Checking", "--income", "--data-dir", str(tmp_path)],
    ]
    for args in txs:
        runner.invoke(cli, ["add"] + args)
    import json
    accounts = {"accounts": [{"name": "Chase-Checking", "type": "checking", "institution": "Chase",
                               "balance": 4200.00, "currency": "USD", "last_updated": "2024-01-15"}]}
    (tmp_path / "accounts.json").write_text(json.dumps(accounts))
    return runner, tmp_path

def test_dashboard_generates_html_file(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    result = runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    assert result.exit_code == 0
    assert os.path.exists(out_path)

def test_dashboard_html_contains_net_worth(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    assert "4,200" in content or "4200" in content

def test_dashboard_is_self_contained(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    # No external CDN links
    assert "cdn.jsdelivr.net" not in content
    assert "cdnjs.cloudflare.com" not in content

def test_dashboard_has_four_tabs(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    assert "tab='overview'" in content or "tab=&apos;overview&apos;" in content or "overview" in content
    assert "Spending" in content
    assert "Goals" in content
    assert "Insights" in content

def test_dashboard_contains_health_score(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    assert "Financial Health Score" in content

def test_dashboard_contains_action_plan_section(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    assert "Action Plan" in content

def test_alpine_js_inlined(runner_with_data, tmp_path):
    runner, data_dir = runner_with_data
    out_path = str(tmp_path / "dashboard.html")
    runner.invoke(cli, ["dashboard", "--output", out_path, "--data-dir", str(data_dir), "--no-open"])
    content = open(out_path).read()
    # Alpine.js is inlined — its signature function name must appear
    assert "Alpine" in content or "alpine" in content.lower()


def test_dashboard_load_files_missing_csv(tmp_path):
    """Cover FileNotFoundError path in _load_files."""
    from dashboard import _load_files
    df, accounts, goals, cards = _load_files(str(tmp_path))
    assert df.empty
    assert accounts == {"accounts": []}
    assert goals["monthly_target"] == 0.0
    assert cards == {"cards": []}


def test_dashboard_load_files_with_goals(tmp_path):
    """Cover goals.json load path in _load_files."""
    import json
    from dashboard import _load_files
    goals_data = {"monthly_target": 300.0, "goals": [], "monthly_streak": {}}
    (tmp_path / "goals.json").write_text(json.dumps(goals_data))
    _, _, goals, cards = _load_files(str(tmp_path))
    assert goals["monthly_target"] == 300.0
    assert cards == {"cards": []}


def test_dashboard_load_files_with_cards(tmp_path):
    """Cover cards.json load path in _load_files."""
    import json
    from dashboard import _load_files
    cards_data = {"cards": [{"name": "Test Card"}]}
    (tmp_path / "cards.json").write_text(json.dumps(cards_data))
    _, _, _, cards = _load_files(str(tmp_path))
    assert cards["cards"][0]["name"] == "Test Card"
