"""Command-line interface for the personal finance tracker."""

import json
import os
import webbrowser
from datetime import date, datetime, timedelta
from typing import Optional

import click
import pandas as pd
from rich.console import Console
from rich.table import Table

from core.categorizer import Categorizer
from core.data_store import DataStore, generate_id
from core.goals import add_named_goal, get_goal_progress, set_monthly_target
from importers.csv_parser import CSVParser
from importers.pdf_parser import PDFParser

console = Console()


def _run_store_import(store: DataStore, transactions: list[dict]) -> tuple[int, int]:
    """
    Add a list of transactions to the store, tracking added and skipped counts.

    Args:
        store: DataStore instance.
        transactions: List of transaction dicts to import.

    Returns:
        (added, skipped) counts.
    """
    added, skipped = 0, 0
    for tx in transactions:
        if store.is_duplicate(tx):
            skipped += 1
        else:
            store.add(tx)
            added += 1
    return added, skipped


@click.group()
def cli() -> None:
    """Personal finance tracker."""
    pass

# ── import ────────────────────────────────────────────────────────────────────

@cli.group()
def import_cmd() -> None:
    """Import transactions from a file."""
    pass

cli.add_command(import_cmd, name="import")

@import_cmd.command("csv")
@click.argument("filepath")
@click.option("--account", required=True, help="Account name (e.g. Chase-Checking)")
@click.option("--bank", required=True, type=click.Choice(["chase", "bofa", "amex"]))
@click.option("--data-dir", default="data", hidden=True)
def import_csv(filepath: str, account: str, bank: str, data_dir: str) -> None:
    """Import a CSV bank statement."""
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    parser = CSVParser()
    transactions = parser.parse(filepath, bank=bank, account=account)
    added, skipped = _run_store_import(store, transactions)
    console.print(f"[green]Imported {added} new transactions[/green] ({skipped} skipped as duplicates)")

@import_cmd.command("pdf")
@click.argument("filepath")
@click.option("--account", required=True, help="Account name (e.g. Chase-Checking)")
@click.option("--bank", required=True, type=click.Choice(["chase", "bofa", "amex"]))
@click.option("--data-dir", default="data", hidden=True)
def import_pdf(filepath: str, account: str, bank: str, data_dir: str) -> None:
    """Import a PDF bank statement."""
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    parser = PDFParser()
    transactions = parser.parse(filepath, bank=bank, account=account)
    added, skipped = _run_store_import(store, transactions)
    console.print(f"[green]Imported {added} new transactions[/green] ({skipped} skipped as duplicates)")

# ── add ───────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--amount", required=True, type=float, help="Amount (negative = expense)")
@click.option("--merchant", required=True)
@click.option("--account", required=True)
@click.option("--category", default=None)
@click.option("--notes", default="")
@click.option("--income", is_flag=True)
@click.option("--savings", is_flag=True)
@click.option("--data-dir", default="data", hidden=True)
def add(amount: float, merchant: str, account: str, category: Optional[str], notes: str, income: bool, savings: bool, data_dir: str) -> None:
    """Manually add a transaction."""
    cat = Categorizer() if category is None else None
    date_str = date.today().isoformat()
    resolved_category = category or (cat.categorize(merchant) if cat else "Other")
    tx = {
        "id": generate_id(date_str, amount, merchant, account),
        "date": date_str,
        "amount": amount,
        "merchant": merchant,
        "category": resolved_category,
        "account": account,
        "source": "manual",
        "is_income": income,
        "is_savings": savings,
        "notes": notes
    }
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    if store.is_duplicate(tx):
        console.print("[yellow]Transaction already exists, skipped.[/yellow]")
    else:
        store.add(tx)
        console.print(f"[green]Added:[/green] {merchant} {amount:+.2f} → {resolved_category}")

# ── summary ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--month", default=None, help="YYYY-MM (defaults to current month)")
@click.option("--data-dir", default="data", hidden=True)
def summary(month: Optional[str], data_dir: str) -> None:
    """Show income vs expenses for a month."""
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    df = store.load()
    if df.empty:
        console.print("[yellow]No transactions found.[/yellow]")
        return
    target_month = month or date.today().strftime("%Y-%m")
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"].dt.strftime("%Y-%m") == target_month]
    income = df[df["amount"] > 0]["amount"].sum()
    expenses = df[df["amount"] < 0]["amount"].sum()
    saved = income + expenses
    t = Table(title=f"Summary — {target_month}", show_header=True)
    t.add_column("", style="bold")
    t.add_column("Amount", justify="right")
    t.add_row("Income", f"[green]${income:.2f}[/green]")
    t.add_row("Expenses", f"[red]${abs(expenses):.2f}[/red]")
    t.add_row("Saved", f"[cyan]${saved:.2f}[/cyan]")
    console.print(t)

# ── top-categories ────────────────────────────────────────────────────────────

@cli.command("top-categories")
@click.option("--last", default="1month", help="e.g. 1month, 3months")
@click.option("--data-dir", default="data", hidden=True)
def top_categories(last: str, data_dir: str) -> None:
    """Show spending ranked by category."""
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    df = store.load()
    if df.empty:
        console.print("[yellow]No transactions found.[/yellow]")
        return
    months = int(last.replace("months", "").replace("month", ""))
    cutoff = (date.today() - timedelta(days=30 * months)).isoformat()
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= cutoff) & (df["amount"] < 0)]
    by_cat = df.groupby("category")["amount"].sum().abs().sort_values(ascending=False)
    t = Table(title=f"Top Categories (last {months} month(s))", show_header=True)
    t.add_column("Category")
    t.add_column("Total", justify="right")
    for cat, total in by_cat.items():
        t.add_row(cat, f"${total:,.2f}")
    console.print(t)

# ── spending ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--category", required=True)
@click.option("--year", default=None, help="YYYY — filter to a specific year")
@click.option("--data-dir", default="data", hidden=True)
def spending(category: str, year: Optional[str], data_dir: str) -> None:
    """Drill into spending for a specific category."""
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    df = store.load()
    if df.empty:
        console.print("[yellow]No transactions found.[/yellow]")
        return
    df["date"] = pd.to_datetime(df["date"])
    mask = (df["category"].str.lower() == category.lower()) & (df["amount"] < 0)
    if year:
        mask &= df["date"].dt.year == int(year)
    subset = df[mask].sort_values("date", ascending=False)
    if subset.empty:
        console.print(f"[yellow]No transactions found for category '{category}'.[/yellow]")
        return
    t = Table(title=f"Spending — {category}{' (' + year + ')' if year else ''}", show_header=True)
    t.add_column("Date")
    t.add_column("Merchant")
    t.add_column("Amount", justify="right")
    for _, row in subset.iterrows():
        t.add_row(str(row["date"].date()), row["merchant"], f"[red]${abs(row['amount']):,.2f}[/red]")
    total = subset["amount"].sum()
    t.add_row("", "[bold]TOTAL[/bold]", f"[bold red]${abs(total):,.2f}[/bold red]")
    console.print(t)

# ── networth ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--data-dir", default="data", hidden=True)
def networth(data_dir: str) -> None:
    """Show net worth across all accounts."""
    accounts_path = f"{data_dir}/accounts.json"
    if not os.path.exists(accounts_path):
        console.print("[yellow]No accounts.json found. Run: finance account update <name> --balance <n>[/yellow]")
        return
    with open(accounts_path) as f:
        data = json.load(f)
    accounts = data.get("accounts", [])
    total = sum(a["balance"] for a in accounts)
    t = Table(title="Net Worth", show_header=True)
    t.add_column("Account")
    t.add_column("Type")
    t.add_column("Balance", justify="right")
    for a in accounts:
        t.add_row(a["name"], a["type"], f"${a['balance']:.2f}")
    t.add_row("", "[bold]TOTAL[/bold]", f"[bold green]${total:.2f}[/bold green]")
    console.print(t)

# ── account ───────────────────────────────────────────────────────────────────

@cli.group()
def account() -> None:
    """Manage accounts."""
    pass

@account.command("update")
@click.argument("name")
@click.option("--balance", required=True, type=float)
@click.option("--type", "account_type", default="checking",
              type=click.Choice(["checking", "savings", "credit", "investment"]))
@click.option("--data-dir", default="data", hidden=True)
def account_update(name: str, balance: float, account_type: str, data_dir: str) -> None:
    """Update or create an account balance."""
    accounts_path = f"{data_dir}/accounts.json"
    if os.path.exists(accounts_path):
        with open(accounts_path) as f:
            data = json.load(f)
    else:
        data = {"accounts": []}
    accounts = data["accounts"]
    existing = next((a for a in accounts if a["name"] == name), None)
    if existing:
        existing["balance"] = balance
        existing["last_updated"] = date.today().isoformat()
    else:
        accounts.append({"name": name, "type": account_type, "institution": name.split("-")[0],
                          "balance": balance, "currency": "USD", "last_updated": date.today().isoformat()})
    with open(accounts_path, "w") as f:
        json.dump(data, f, indent=2)
    console.print(f"[green]Updated {name}: ${balance:,.2f}[/green]")

# ── tag ───────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("transaction_id")
@click.option("--income", is_flag=True)
@click.option("--savings", is_flag=True)
@click.option("--data-dir", default="data", hidden=True)
def tag(transaction_id: str, income: bool, savings: bool, data_dir: str) -> None:
    """Tag a transaction as income or savings."""
    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    fields = {}
    if income:
        fields["is_income"] = True
    if savings:
        fields["is_savings"] = True
    if not fields:
        console.print("[yellow]Specify --income or --savings[/yellow]")
        return
    store.update(transaction_id, fields)
    console.print(f"[green]Tagged transaction {transaction_id[:8]}...[/green]")

# ── goal ──────────────────────────────────────────────────────────────────────

@cli.group()
def goal() -> None:
    """Manage savings goals."""
    pass

@goal.command("set")
@click.argument("name")
@click.option("--amount", type=float, default=None, help="Monthly savings target (use with 'monthly')")
@click.option("--target", type=float, default=None, help="Named goal target amount")
@click.option("--by", "deadline", default=None, help="Deadline YYYY-MM for named goal")
@click.option("--data-dir", default="data", hidden=True)
def goal_set(name: str, amount: Optional[float], target: Optional[float], deadline: Optional[str], data_dir: str) -> None:
    """Set a monthly savings target or a named goal."""
    if name == "monthly":
        if amount is None:
            console.print("[red]--amount required for monthly goal[/red]")
            return
        set_monthly_target(amount, data_dir)
        console.print(f"[green]Monthly savings target set: ${amount:,.2f}[/green]")
    else:
        if target is None or deadline is None:
            console.print("[red]--target and --by required for named goal[/red]")
            return
        add_named_goal(name, target, deadline, data_dir)
        console.print(f"[green]Goal '{name}' set: ${target:,.2f} by {deadline}[/green]")

@goal.command("status")
@click.option("--data-dir", default="data", hidden=True)
def goal_status(data_dir: str) -> None:
    """Show progress on all savings goals."""
    data = get_goal_progress(data_dir)
    monthly = data.get("monthly_target", 0)
    streak = data.get("monthly_streak", {})
    console.print(f"\n[bold]Monthly target:[/bold] ${monthly:,.2f}/month  |  Streak: {streak.get('current', 0)} months\n")
    goals = data.get("goals", [])
    if not goals:
        console.print("[yellow]No named goals set. Use: finance goal set \"Goal Name\" --target 5000 --by 2025-06[/yellow]")
        return
    t = Table(title="Savings Goals", show_header=True)
    t.add_column("Goal")
    t.add_column("Progress", justify="right")
    t.add_column("Target", justify="right")
    t.add_column("% Done", justify="right")
    t.add_column("Deadline")
    for g in goals:
        pct = (g["current_amount"] / g["target_amount"] * 100) if g["target_amount"] > 0 else 0
        t.add_row(g["name"], f"${g['current_amount']:,.2f}",
                  f"${g['target_amount']:,.2f}", f"{pct:.0f}%", g["deadline"])
    console.print(t)

# ── dashboard ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--output", default="reports/dashboard.html")
@click.option("--data-dir", default="data", hidden=True)
@click.option("--no-open", is_flag=True, hidden=True)
def dashboard(output: str, data_dir: str, no_open: bool) -> None:
    """Generate and open the HTML dashboard."""
    from dashboard import build_dashboard
    path = build_dashboard(data_dir=data_dir, output_path=output)
    console.print(f"[green]Dashboard generated:[/green] {path}")
    if not no_open:
        webbrowser.open(f"file://{os.path.abspath(path)}")

# ── cards ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--data-dir", default="data", hidden=True)
def cards(data_dir: str) -> None:
    """Show credit card portfolio, optimizer, and upgrade recommendations."""
    from core.cards import load_cards
    from dashboard.analytics import compute_card_intelligence

    card_data = load_cards(f"{data_dir}/cards.json")
    if not card_data.get("cards"):
        console.print("[yellow]No cards configured. Copy data/cards.example.json to data/cards.json and edit.[/yellow]")
        return

    store = DataStore(transactions_path=f"{data_dir}/transactions.csv")
    df = store.load()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])

    intel = compute_card_intelligence(df, card_data)

    # Portfolio table
    t = Table(title="Card Portfolio", show_header=True)
    t.add_column("Card")
    t.add_column("Annual Fee", justify="right")
    t.add_column("Est. Rewards/yr", justify="right")
    t.add_column("Net Value", justify="right")
    for cv in intel["card_values"]:
        color = "green" if cv["net_value"] > 0 else "red"
        t.add_row(
            cv["name"],
            f"${cv['annual_fee']:.2f}",
            f"${cv['gross_rewards']:.2f}",
            f"[{color}]${cv['net_value']:.2f}[/{color}]",
        )
    console.print(t)

    # Missed rewards callout
    if intel["missed_rewards_annual"] >= 5:
        console.print(
            f"\n[yellow]You're leaving [bold]${intel['missed_rewards_annual']:.2f}[/bold]/yr "
            "on the table by not using the optimal card per category.[/yellow]"
        )

    # Top 3 category optimizations
    top_opts = [o for o in intel["optimal_per_category"][:3] if o["annual_gain"] > 0]
    if top_opts:
        t2 = Table(title="Category Optimizer (Top 3)", show_header=True)
        t2.add_column("Category")
        t2.add_column("Use This Card")
        t2.add_column("Annual Gain", justify="right")
        for item in top_opts:
            t2.add_row(item["category"], item["best_card"], f"[green]+${item['annual_gain']:.2f}[/green]")
        console.print(t2)

    # Top upgrade recommendation
    if intel["upgrade_recommendations"]:
        rec = intel["upgrade_recommendations"][0]
        console.print(
            f"\n[blue]Top upgrade:[/blue] {rec['name']} — {rec['why']} "
            f"(+${rec['gain_over_best']:.2f}/yr over your best card)"
        )


if __name__ == "__main__":  # pragma: no cover
    cli()
