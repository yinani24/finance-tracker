"""Run once to generate PDF fixtures for tests.

Usage:
    python tests/fixtures/make_pdf_fixtures.py
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle


def make_chase_pdf(path: str) -> None:
    """Generate a Chase credit card PDF fixture (table format)."""
    doc = SimpleDocTemplate(path, pagesize=letter)
    data = [
        ["Transaction Date", "Description", "Amount"],
        ["01/15/2024", "CHIPOTLE #1234", "-45.20"],
        ["01/16/2024", "NETFLIX.COM", "-15.99"],
        ["01/17/2024", "DIRECT DEPOSIT", "2500.00"],
    ]
    table = Table(data)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
    doc.build([table])


def make_bofa_visa_pdf(path: str) -> None:
    """Generate a BofA Visa credit card PDF fixture (regex line format)."""
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=letter)
    lines = [
        "Purchases and Adjustments",
        "01/10 01/11 WHOLE FOODS 1234 5678 56.34",
        "01/12 01/13 AMAZON.COM 2345 6789 89.99",
        "Payments and Other Credits",
    ]
    story = [Paragraph(line, styles["Normal"]) for line in lines]
    doc.build(story)


def make_bofa_checking_pdf(path: str) -> None:
    """Generate a BofA checking/savings PDF fixture."""
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=letter)
    lines = [
        "Account number: 0000 0000 1234",
        "01/05/26 CENTAVO PAYROLL 3200.00",
        "01/07/26 CHIPOTLE -12.50",
        "01/10/26 ROBINHOOD -500.00",
    ]
    story = [Paragraph(line, styles["Normal"]) for line in lines]
    doc.build(story)


def make_robinhood_pdf(path: str) -> None:
    """Generate a Robinhood brokerage PDF fixture with Account Activity section."""
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=letter)
    lines = [
        "Account Activity",
        "Gold Subscription Margin Cash 01/05/2026 $5.00",
        "Interest Payment Margin Cash 01/15/2026 $1.23",
        "Executed Trades",
    ]
    story = [Paragraph(line, styles["Normal"]) for line in lines]
    doc.build(story)


def make_chase_bank_pdf(path: str) -> None:
    """Generate a Chase Bank combined checking/savings PDF fixture."""
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=letter)
    lines = [
        "CHASE SECURE CHECKING",
        "TRANSACTION DETAIL",
        "Beginning Balance 235.88",
        "12/18 Centavo Inc Payroll 1000.00 1235.88",
        "01/08 Monthly Service Fee -4.95 1230.93",
        "Online Transfer From Sav 1000.00 2230.93",
        "Ending Balance 2230.93",
        "CHASE SAVINGS",
        "TRANSACTION DETAIL",
        "Beginning Balance 527.99",
        "12/18 Centavo Inc Payroll PPD ID: 9117571000 250.00 777.99",
        "12/19 Online Transfer To Chk -250.00 527.99",
        "Ending Balance 527.99",
    ]
    story = [Paragraph(line, styles["Normal"]) for line in lines]
    doc.build(story)


def make_amex_hysa_pdf(path: str) -> None:
    """Generate an Amex High Yield Savings Account PDF fixture."""
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=letter)
    lines = [
        "Account Activity",
        "Date Transactions Debits Credits Balance",
        "01/03/2026 Beginning Balance $10036.68",
        "02/02/2026 Interest Payment $27.71 $10064.39",
        "02/02/2026 Ending Balance $10064.39",
    ]
    story = [Paragraph(line, styles["Normal"]) for line in lines]
    doc.build(story)


if __name__ == "__main__":
    make_chase_pdf("tests/fixtures/chase_sample.pdf")
    make_bofa_visa_pdf("tests/fixtures/bofa_visa_sample.pdf")
    make_bofa_checking_pdf("tests/fixtures/bofa_checking_sample.pdf")
    make_robinhood_pdf("tests/fixtures/robinhood_sample.pdf")
    make_chase_bank_pdf("tests/fixtures/chase_bank_sample.pdf")
    make_amex_hysa_pdf("tests/fixtures/amex_hysa_sample.pdf")
    print("PDF fixtures created.")
