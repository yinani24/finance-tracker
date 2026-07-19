"""Manual bank-statement import (CSV) — the Plaid-free ingest path.

Parses a single-signed-amount CSV export into deduplicated ``Transaction`` rows
under a chosen account, reusing the same dedupe fingerprint and enrichment hook
as the Plaid sync path so imported transactions behave identically downstream
(categorization, spending profile, recommendations).

Amount convention (slice 1): the CSV ``amount`` column is read as
**negative = money out (spend), positive = money in (income)**, matching the
app-internal ``Transaction.amount`` sign. Banks vary here; the column-mapping +
preview slice (issue #22, slice 2) will let the user confirm/flip the sign for
exports that use the opposite convention.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.import_record import Import
from app.models.transaction import Transaction
from app.repositories.import_record import ImportRepository
from app.services.dedupe import generate_dedupe_hash
from app.services.enrichment import EnrichmentInput
from app.services.enrichment.apply import apply_enrichment
from app.services.file_storage import save_upload

PROVIDER = "manual"
IMPORT_TYPE = "csv"

# Header aliases matched case-insensitively (substring for date, exact-ish for
# the others) against the CSV's column names. Kept intentionally small for
# slice 1; arbitrary layouts are the job of the column-mapping slice.
_DATE_HINTS = ("date",)
_DESC_HINTS = ("description", "merchant", "name", "payee", "memo", "details")
# A single signed-amount column (negative = spend).
_AMOUNT_HINTS = ("amount", "value")
# Some banks export two magnitude columns instead of one signed column.
_DEBIT_HINTS = ("debit", "withdrawal")
_CREDIT_HINTS = ("credit", "deposit")

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%Y/%m/%d",
    "%b %d, %Y",
    "%d %b %Y",
)


class StatementParseError(Exception):
    """Raised when a file cannot be parsed at all (bad header / empty / binary).

    Distinct from a per-row parse failure, which is counted as ``skipped`` and
    does not abort the import.
    """


@dataclass
class ParsedRow:
    occurred_on: date
    merchant: str
    # Stored-amount convention: negative = spend, positive = income.
    signed_amount: float


@dataclass
class RowError:
    """A single data row that couldn't be parsed, with why.

    ``row`` is the 1-based line number in the uploaded file (the header is
    row 1, so the first data row is row 2), so the user can locate the
    offending line in their statement.
    """

    row: int
    reason: str


@dataclass
class ImportResult:
    total_rows: int
    added: int
    duplicates: int
    skipped: int
    # Per-row parse failures (row number + reason). ``len(errors) == skipped``;
    # ``skipped`` is retained for back-compat with existing summary consumers.
    errors: list[RowError]


def _match_column(fieldnames: list[str], hints: tuple[str, ...]) -> str | None:
    """Return the column best matching ``hints``, honoring hint priority.

    Hints are tried in order, so a higher-priority hint wins even if a
    lower-priority one appears earlier among the columns (e.g. ``Description``
    beats a ``Details`` transaction-type column).
    """
    normalized = [(name, (name or "").strip().lower()) for name in fieldnames]
    for hint in hints:
        for name, norm in normalized:
            if hint in norm:
                return name
    return None


def _parse_amount(raw: str) -> float:
    """Parse a currency string into a float (negative = spend).

    Tolerates ``$``/currency symbols, thousands separators, whitespace, and
    accounting-style parentheses (``(50.00)`` → ``-50.00``). Raises ``ValueError``
    on an empty or non-numeric value so the caller can skip that row.
    """
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty amount")
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    text = text.replace("$", "").replace(",", "").replace(" ", "")
    if not text:
        raise ValueError("empty amount")
    value = float(text)
    return -value if negative else value


def _parse_amount_or_zero(raw: str) -> float:
    """Like ``_parse_amount`` but treats an empty cell as ``0.0``.

    Used for two-column debit/credit layouts where a given row populates only
    one of the two columns.
    """
    if not (raw or "").strip():
        return 0.0
    return _parse_amount(raw)


def _parse_date(raw: str) -> date:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty date")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date format: {text!r}")


def parse_csv(content: bytes) -> tuple[list[ParsedRow], list[RowError]]:
    """Parse CSV bytes into ``ParsedRow``s plus a list of per-row parse errors.

    Raises ``StatementParseError`` if the file is empty/undecodable or lacks the
    required date / description / amount columns. Individual rows that fail to
    parse are collected as ``RowError`` (row number + reason), never aborting the
    whole file — the count of these is the import's ``skipped`` total.
    """
    if not content or not content.strip():
        raise StatementParseError("file is empty")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise StatementParseError("file is not valid UTF-8 text") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise StatementParseError("no CSV header row found")

    fieldnames = list(reader.fieldnames)
    date_col = _match_column(fieldnames, _DATE_HINTS)
    desc_col = _match_column(fieldnames, _DESC_HINTS)
    amount_col = _match_column(fieldnames, _AMOUNT_HINTS)
    debit_col = _match_column(fieldnames, _DEBIT_HINTS)
    credit_col = _match_column(fieldnames, _CREDIT_HINTS)
    # Prefer a single signed amount column; otherwise fall back to a
    # debit/credit magnitude pair (spend = debit, income = credit).
    has_amount = amount_col is not None or debit_col is not None or credit_col is not None
    missing = [
        label
        for label, col in (
            ("date", date_col),
            ("description", desc_col),
            ("amount", "present" if has_amount else None),
        )
        if col is None
    ]
    if missing:
        raise StatementParseError(
            "missing required column(s): " + ", ".join(missing)
        )

    rows: list[ParsedRow] = []
    errors: list[RowError] = []
    # Data rows start at file line 2 (line 1 is the header).
    for line_no, raw_row in enumerate(reader, start=2):
        try:
            occurred_on = _parse_date(raw_row.get(date_col, ""))
            if amount_col is not None:
                signed_amount = _parse_amount(raw_row.get(amount_col, ""))
            else:
                # Two-column debit/credit: spend is negative, income positive.
                # Use magnitudes so either column's sign representation works.
                debit_raw = raw_row.get(debit_col, "") if debit_col else ""
                credit_raw = raw_row.get(credit_col, "") if credit_col else ""
                if not (debit_raw or "").strip() and not (credit_raw or "").strip():
                    raise ValueError("empty amount")
                debit = abs(_parse_amount_or_zero(debit_raw))
                credit = abs(_parse_amount_or_zero(credit_raw))
                signed_amount = credit - debit
        except ValueError as exc:
            errors.append(RowError(row=line_no, reason=str(exc)))
            continue
        merchant = (raw_row.get(desc_col) or "").strip() or "Unknown"
        rows.append(
            ParsedRow(
                occurred_on=occurred_on,
                merchant=merchant,
                signed_amount=signed_amount,
            )
        )
    return rows, errors


def _persist_rows(
    db: Session,
    user_id: int,
    account_id: int,
    import_id: int,
    parsed: list[ParsedRow],
) -> tuple[int, int]:
    """Insert deduped transactions; return (added, duplicates)."""
    added = 0
    duplicates = 0
    new_rows: list[tuple[Transaction, EnrichmentInput]] = []
    for row in parsed:
        # Feed the hasher the Plaid "outflow-positive" convention so a CSV row
        # and its Plaid twin for the same purchase collapse to one hash.
        outflow_amount = -row.signed_amount
        dedupe_hash = generate_dedupe_hash(
            row.occurred_on.isoformat(), outflow_amount, row.merchant, account_id
        )
        existing = db.scalars(
            select(Transaction).where(
                Transaction.dedupe_hash == dedupe_hash,
                Transaction.user_id == user_id,
            )
        ).first()
        if existing:
            duplicates += 1
            continue
        txn = Transaction(
            user_id=user_id,
            account_id=account_id,
            occurred_on=row.occurred_on,
            amount=row.signed_amount,
            merchant=row.merchant,
            normalized_merchant=row.merchant.lower().strip(),
            category=None,
            is_income=row.signed_amount > 0,
            is_savings=False,
            source="import",
            source_import_id=import_id,
            dedupe_hash=dedupe_hash,
        )
        db.add(txn)
        new_rows.append(
            (
                txn,
                EnrichmentInput(
                    merchant=row.merchant,
                    amount=row.signed_amount,
                    plaid_category=None,
                ),
            )
        )
        added += 1

    # Enrich before commit so enriched category / merchant persist in the same
    # transaction as the insert (no-op with the default provider).
    apply_enrichment(new_rows)
    db.commit()
    return added, duplicates


def run_import(
    db: Session,
    user_id: int,
    account_id: int,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
) -> tuple[Import, ImportResult]:
    """Persist an ``Import`` + file, parse the CSV, and ingest transactions.

    On a parse failure the import is recorded with ``status="failed"`` and
    ``StatementParseError`` is re-raised (no partial transactions are written);
    otherwise the import is marked ``done`` and an ``ImportResult`` returned.
    The caller is responsible for verifying ``account_id`` belongs to the user
    before calling this.
    """
    repo = ImportRepository(db)
    record = repo.create(user_id, account_id, PROVIDER, IMPORT_TYPE)
    storage_key = save_upload(file_bytes, filename)
    repo.add_file(
        import_id=record.id,
        storage_key=storage_key,
        original_filename=filename or "upload.csv",
        mime_type=mime_type or "text/csv",
        size_bytes=len(file_bytes),
    )

    try:
        parsed, errors = parse_csv(file_bytes)
    except StatementParseError as exc:
        repo.mark_failed(record, str(exc))
        raise

    added, duplicates = _persist_rows(db, user_id, account_id, record.id, parsed)
    repo.mark_done(record)
    result = ImportResult(
        total_rows=len(parsed) + len(errors),
        added=added,
        duplicates=duplicates,
        skipped=len(errors),
        errors=errors,
    )
    return record, result
