"""Thin orchestrator that loads data files and renders the Jinja2 dashboard template."""
import json
import os
import pandas as pd
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from dashboard.analytics import build_context

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


def _load_files(data_dir: str) -> tuple[pd.DataFrame, dict, dict]:
    """Load transactions, accounts, and goals from the data directory.

    Args:
        data_dir: Path to the directory containing transactions.csv, accounts.json, and goals.json.

    Returns:
        A 3-tuple of (transactions DataFrame, accounts dict, goals dict).
    """
    store_path    = f"{data_dir}/transactions.csv"
    accounts_path = f"{data_dir}/accounts.json"
    goals_path    = f"{data_dir}/goals.json"

    try:
        df = pd.read_csv(store_path)
        df["date"] = pd.to_datetime(df["date"])
    except FileNotFoundError:
        df = pd.DataFrame()

    accounts = {"accounts": []}
    if os.path.exists(accounts_path):
        with open(accounts_path) as f:
            accounts = json.load(f)

    goals = {"monthly_target": 0.0, "goals": [], "monthly_streak": {}}
    if os.path.exists(goals_path):
        with open(goals_path) as f:
            goals = json.load(f)

    return df, accounts, goals


def build_dashboard(data_dir: str = "data", output_path: str = "reports/dashboard.html") -> str:
    """Build the HTML dashboard by loading data and rendering the Jinja2 template.

    Args:
        data_dir: Directory containing the data files (transactions.csv, accounts.json, goals.json).
        output_path: File path where the rendered HTML report will be written.

    Returns:
        The output_path where the HTML file was written.
    """
    df, accounts, goals = _load_files(data_dir)
    context = build_context(df, accounts, goals)

    env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR))
    env.filters["format_currency"] = lambda v: f"{v:,.2f}"
    template = env.get_template("dashboard.html.j2")

    def _read(filename: str) -> str:
        """Read a template asset file and return its contents as a string.

        Args:
            filename: Name of the file inside the templates directory.

        Returns:
            The full text content of the file.
        """
        with open(os.path.join(_TEMPLATES_DIR, filename)) as f:
            return f.read()

    html = template.render(
        **context,
        chartjs=_read("chart.min.js"),
        daisyui_css=_read("daisyui.min.css"),
        alpine_js=_read("alpine.min.js"),
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    return output_path
