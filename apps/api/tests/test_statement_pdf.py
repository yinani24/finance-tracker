from unittest.mock import patch

import pytest

from app.services.statement_import import StatementParseError
from app.services.statement_pdf import (
    _extract_json_array,
    _heuristic_rows,
    extract_text,
    parse_pdf,
)


class TestExtractJsonArray:
    def test_plain_array(self):
        assert _extract_json_array('[{"a": 1}]') == [{"a": 1}]

    def test_tolerates_prose_and_markdown_fences(self):
        raw = 'Sure, here are the transactions:\n```json\n[{"date": "2026-07-01"}]\n```'
        assert _extract_json_array(raw) == [{"date": "2026-07-01"}]

    def test_no_array_raises(self):
        with pytest.raises(StatementParseError):
            _extract_json_array("there is no json here")


class TestExtractText:
    def test_non_pdf_bytes_raise(self):
        with pytest.raises(StatementParseError):
            extract_text(b"this is plainly not a PDF file")


class TestHeuristicRows:
    def test_parses_date_led_lines_first_amount_wins(self):
        text = (
            "DEMO BANK Statement\n"
            "Date Description Amount Balance\n"
            "07/01/2026 ACME PAYROLL 3,200.00 3,200.00\n"
            "07/03/2026 CHIPOTLE 452 -12.65 3,187.35\n"
            "not a transaction line\n"
        )
        rows, errors = _heuristic_rows(text)
        by = {r.merchant: r.signed_amount for r in rows}
        # first money after the date is the amount; the balance column is ignored
        assert by["ACME PAYROLL"] == 3200.00
        assert by["CHIPOTLE 452"] == -12.65
        assert errors == []

    def test_trailing_minus_is_negative(self):
        rows, _ = _heuristic_rows("07/04/2026 STORE 42.00-\n")
        assert rows[0].signed_amount == -42.00


class TestParsePdf:
    def test_empty_file_raises(self):
        with pytest.raises(StatementParseError):
            parse_pdf(b"   ")

    def test_heuristic_path_does_not_call_the_llm(self):
        text = "07/03/2026 CHIPOTLE 452 -12.65\n"
        with patch(
            "app.services.statement_pdf.extract_text", return_value=text
        ), patch(
            "app.services.statement_pdf._llm_extract_rows",
            side_effect=AssertionError("LLM must not be called when heuristic works"),
        ):
            rows, errors = parse_pdf(b"%PDF-1.4 fake")
        assert len(rows) == 1 and rows[0].signed_amount == -12.65

    def test_maps_llm_items_to_rows_with_sign_and_dates(self):
        items = [
            {"date": "2026-07-03", "description": "CHIPOTLE 452", "amount": -12.65},
            {"date": "07/01/2026", "description": "ACME PAYROLL", "amount": 3200.0},
            {"bad": "not a transaction object"},
            {"date": "notadate", "description": "X", "amount": -1},
        ]
        with patch(
            "app.services.statement_pdf.extract_text", return_value="statement text"
        ), patch(
            "app.services.statement_pdf._llm_extract_rows", return_value=items
        ):
            rows, errors = parse_pdf(b"%PDF-1.4 fake bytes")

        assert len(rows) == 2
        by_merchant = {r.merchant: r.signed_amount for r in rows}
        assert by_merchant["CHIPOTLE 452"] == -12.65  # spend stays negative
        assert by_merchant["ACME PAYROLL"] == 3200.0  # income positive
        # the non-dict item and the bad-date item are reported, not dropped silently
        assert len(errors) == 2

    def test_missing_api_key_raises(self):
        from app.config import settings

        original = settings.anthropic_api_key
        settings.anthropic_api_key = ""
        try:
            with patch(
                "app.services.statement_pdf.extract_text", return_value="text"
            ):
                with pytest.raises(StatementParseError):
                    parse_pdf(b"%PDF-1.4 fake")
        finally:
            settings.anthropic_api_key = original
