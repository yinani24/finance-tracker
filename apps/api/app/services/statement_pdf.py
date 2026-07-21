"""PDF bank/card statement parsing via text extraction + an LLM.

Bank and credit-card statement PDFs have no consistent layout, so instead of
brittle regex we extract the page text and ask the model (the same Anthropic
integration the chat feature uses) to return structured transactions. The output
is coerced through the same date/amount parsers and ``ParsedRow`` shape as the
CSV path, so the rest of the import pipeline (dedup, enrichment, storage) is
unchanged. The model is instructed on our sign convention (negative = spend),
which also sidesteps the CSV credit-card sign ambiguity.
"""

from __future__ import annotations

import io
import json
import logging
import re

from app.config import settings
from app.services.statement_import import (
    ParsedRow,
    RowError,
    StatementParseError,
    _parse_amount,
    _parse_date,
)

logger = logging.getLogger(__name__)

# A line that begins with a transaction date. Handles full dates (MM/DD/YY,
# YYYY-MM-DD) and the bare MM/DD that credit-card statements (e.g. Chase) use.
_LINE_DATE = re.compile(
    r"^\s*(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2})"
    r"\s+(?P<rest>.+)$"
)
# A currency amount: optional $, thousands separators, 2 decimals, optional
# leading/trailing minus or accounting parentheses.
_MONEY = re.compile(r"-?\(?\$?\d[\d,]*\.\d{2}\)?-?")
# A full date anywhere in the text, used to infer the year for bare MM/DD rows.
_ANY_FULL_DATE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-](\d{2,4})\b")

# Current Anthropic model for statement extraction (overridable via env).
_MODEL = settings.pdf_import_model or "claude-sonnet-5"

_SYSTEM = (
    "You extract financial transactions from bank and credit-card statement text. "
    "Return ONLY a JSON array, no prose, no markdown fences. Each element is an "
    'object: {"date": "YYYY-MM-DD", "description": "<merchant or description>", '
    '"amount": <number>}. Sign convention: amount is NEGATIVE for money leaving '
    "the account (purchases, withdrawals, payments, fees, interest charged) and "
    "POSITIVE for money coming in (deposits, income, refunds, statement credits). "
    "Normalize every date to YYYY-MM-DD (infer the year from the statement if a "
    "row omits it). Include every real transaction line. EXCLUDE summary lines, "
    "running balances, subtotals, headers, and payment-due/minimum lines. If there "
    "are no transactions, return []."
)


def extract_text(pdf_bytes: bytes) -> str:
    """Extract text from a PDF's pages. Raises ``StatementParseError`` if the
    file isn't a readable PDF or yields no extractable text (e.g. a scanned
    image, which would need OCR)."""
    import pdfplumber  # imported lazily so CSV-only deployments needn't load it

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:  # pdfminer raises a variety of parse errors
        raise StatementParseError("could not read PDF file") from exc

    text = "\n".join(pages).strip()
    if not text:
        raise StatementParseError(
            "no extractable text in PDF (a scanned/image statement would need OCR)"
        )
    return text


def _extract_json_array(raw: str) -> list:
    """Pull the JSON array out of the model response, tolerating stray prose or
    markdown fences around it."""
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise StatementParseError("could not parse transactions from the statement")
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise StatementParseError(
            "could not parse transactions from the statement"
        ) from exc
    if not isinstance(data, list):
        raise StatementParseError("could not parse transactions from the statement")
    return data


def _llm_extract_rows(text: str) -> list[dict]:
    if not settings.anthropic_api_key:
        raise StatementParseError(
            "PDF import needs FT_ANTHROPIC_API_KEY to be configured"
        )
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        message = client.messages.create(
            model=_MODEL,
            max_tokens=8192,
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": "Extract the transactions from this statement:\n\n"
                    + text,
                }
            ],
        )
    except anthropic.AnthropicError as exc:
        logger.warning("PDF LLM extraction failed: %s", exc)
        raise StatementParseError("PDF statement extraction failed") from exc

    raw = "".join(
        block.text for block in message.content if getattr(block, "type", "") == "text"
    )
    return _extract_json_array(raw)


def parse_pdf(
    pdf_bytes: bytes, is_credit: bool = False
) -> tuple[list[ParsedRow], list[RowError]]:
    """Parse a PDF statement into ``ParsedRow``s + per-row errors, mirroring
    :func:`statement_import.parse_csv` so the rest of the pipeline is identical.

    ``is_credit`` flips the amount sign, because credit-card statements list
    purchases as positive and payments/credits as negative — the opposite of our
    ``negative = spend`` convention.

    Raises ``StatementParseError`` for whole-file failures (unreadable PDF, no
    text, missing API key, unparseable model output); individual bad items are
    collected as ``RowError`` and do not abort the import.
    """
    if not pdf_bytes or not pdf_bytes.strip():
        raise StatementParseError("file is empty")

    text = extract_text(pdf_bytes)

    # Free path first: regex-parse date-led lines. Works for common statement
    # layouts (incl. Chase-style MM/DD credit-card rows) with no API cost. Only
    # fall back to the (paid) LLM when the heuristic finds nothing.
    rows, errors = _heuristic_rows(text, flip_sign=is_credit)
    if rows:
        return rows, errors

    llm_rows, llm_errors = _items_to_rows(_llm_extract_rows(text))
    if is_credit:
        llm_rows = [
            ParsedRow(
                occurred_on=r.occurred_on,
                merchant=r.merchant,
                signed_amount=-r.signed_amount,
            )
            for r in llm_rows
        ]
    return llm_rows, llm_errors


def _infer_year(text: str) -> int | None:
    """Best-effort statement year, to fill in bare ``MM/DD`` rows. Uses the first
    full date found (e.g. an Opening/Closing date), normalizing 2-digit years."""
    m = _ANY_FULL_DATE.search(text)
    if not m:
        return None
    year = int(m.group(1))
    return 2000 + year if year < 100 else year


def _heuristic_rows(
    text: str, flip_sign: bool = False
) -> tuple[list[ParsedRow], list[RowError]]:
    """Parse transactions from date-led statement lines with no LLM.

    For each line beginning with a date, the LAST money amount on the line is
    the transaction amount (statement descriptions can contain digits/phone
    numbers, but the amount is the trailing column). Bare ``MM/DD`` dates get the
    statement year inferred. ``flip_sign`` inverts the sign for credit cards.
    """
    year = _infer_year(text)
    rows: list[ParsedRow] = []
    for line in text.splitlines():
        m = _LINE_DATE.match(line)
        if not m:
            continue
        rest = m.group("rest")
        money = list(_MONEY.finditer(rest))
        if not money:
            continue
        last = money[-1]
        amount_token = last.group(0)
        # trailing-minus convention (e.g. "12.65-") → negative
        if amount_token.endswith("-"):
            amount_token = "-" + amount_token[:-1]
        description = rest[: last.start()].strip() or "Unknown"
        date_str = m.group("date")
        # A bare MM/DD (credit-card style) gets the inferred statement year.
        if date_str.count("/") == 1 and date_str.count("-") == 0:
            if year is None:
                continue
            date_str = f"{date_str}/{year}"
        try:
            occurred_on = _parse_date(date_str)
            signed_amount = _parse_amount(amount_token)
        except ValueError:
            continue
        if flip_sign:
            signed_amount = -signed_amount
        rows.append(
            ParsedRow(
                occurred_on=occurred_on,
                merchant=description,
                signed_amount=signed_amount,
            )
        )
    return rows, []


def _items_to_rows(items: list) -> tuple[list[ParsedRow], list[RowError]]:
    """Coerce LLM-returned transaction dicts into ``ParsedRow``s."""
    rows: list[ParsedRow] = []
    errors: list[RowError] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(RowError(row=idx, reason="not a transaction object"))
            continue
        try:
            occurred_on = _parse_date(str(item.get("date", "")))
            signed_amount = _parse_amount(str(item.get("amount", "")))
        except ValueError as exc:
            errors.append(RowError(row=idx, reason=str(exc)))
            continue
        merchant = str(item.get("description") or "").strip() or "Unknown"
        rows.append(
            ParsedRow(
                occurred_on=occurred_on,
                merchant=merchant,
                signed_amount=signed_amount,
            )
        )
    return rows, errors
