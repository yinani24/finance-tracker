"""Run once to generate PDF fixtures for tests.

Usage:
    python tests/fixtures/make_pdf_fixtures.py
"""
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


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


if __name__ == "__main__":
    make_chase_pdf("tests/fixtures/chase_sample.pdf")
    make_bofa_visa_pdf("tests/fixtures/bofa_visa_sample.pdf")
    make_bofa_checking_pdf("tests/fixtures/bofa_checking_sample.pdf")
    make_robinhood_pdf("tests/fixtures/robinhood_sample.pdf")
    print("PDF fixtures created.")
