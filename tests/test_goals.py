import pytest
import json
from click.testing import CliRunner
from main import cli

@pytest.fixture
def runner():
    return CliRunner()

def test_set_monthly_goal(runner, tmp_path):
    result = runner.invoke(cli, ["goal", "set", "monthly", "--amount", "500", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    goals = json.loads((tmp_path / "goals.json").read_text())
    assert goals["monthly_target"] == 500.0

def test_set_named_goal(runner, tmp_path):
    result = runner.invoke(cli, ["goal", "set", "Emergency Fund", "--target", "10000", "--by", "2025-06", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    goals = json.loads((tmp_path / "goals.json").read_text())
    assert goals["goals"][0]["name"] == "Emergency Fund"
    assert goals["goals"][0]["target_amount"] == 10000.0

def test_goal_status_shows_progress(runner, tmp_path):
    runner.invoke(cli, ["goal", "set", "Emergency Fund", "--target", "10000", "--by", "2025-06", "--data-dir", str(tmp_path)])
    result = runner.invoke(cli, ["goal", "status", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Emergency Fund" in result.output
