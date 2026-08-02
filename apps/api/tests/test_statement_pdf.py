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
    def test_parses_date_led_lines_trailing_amount(self):
        text = (
            "DEMO STATEMENT\n"
            "07/01/2026 ACME PAYROLL 3,200.00\n"
            "07/03/2026 CHIPOTLE 452 -12.65\n"
            "not a transaction line\n"
        )
        rows, errors = _heuristic_rows(text)
        by = {r.merchant: r.signed_amount for r in rows}
        assert by["ACME PAYROLL"] == 3200.00
        assert by["CHIPOTLE 452"] == -12.65
        assert errors == []

    def test_trailing_minus_is_negative(self):
        rows, _ = _heuristic_rows("07/04/2026 STORE 42.00-\n")
        assert rows[0].signed_amount == -42.00

    def test_bare_mmdd_gets_inferred_statement_year(self):
        # Credit-card statements use MM/DD with no year; infer it from a full
        # date elsewhere in the text (e.g. the Opening/Closing line).
        text = "Opening/Closing Date 06/05/26 - 07/04/26\n06/06 SQ *COFFEE BAR 8.56\n"
        rows, _ = _heuristic_rows(text)
        assert rows[0].occurred_on.isoformat() == "2026-06-06"
        assert rows[0].signed_amount == 8.56

    def test_credit_flip_inverts_sign(self):
        # Credit-card convention: purchase positive -> spend (negative);
        # payment negative -> credit (positive).
        text = (
            "Opening/Closing Date 06/05/26 - 07/04/26\n"
            "06/06 SQ *COFFEE BAR 8.56\n"
            "06/07 PAYMENT THANK YOU -100.00\n"
        )
        rows, _ = _heuristic_rows(text, flip_sign=True)
        by = {r.merchant: r.signed_amount for r in rows}
        assert by["SQ *COFFEE BAR"] == -8.56
        assert by["PAYMENT THANK YOU"] == 100.00


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


class TestCreditSignHandling:
    """#203: only the heuristic path flips signs; the LLM path is already
    normalized by its system prompt, so flipping again inverted every spend."""

    def test_llm_path_is_not_sign_flipped_for_credit_accounts(self):
        # Model returns OUR convention already: purchase negative, payment positive.
        items = [
            {"date": "2026-07-01", "description": "COFFEE BAR", "amount": -8.56},
            {"date": "2026-07-02", "description": "PAYMENT THANK YOU", "amount": 100.0},
        ]
        with patch(
            "app.services.statement_pdf.extract_text", return_value="no date-led lines"
        ), patch(
            "app.services.statement_pdf._heuristic_rows", return_value=([], [])
        ), patch(
            "app.services.statement_pdf._llm_extract_rows", return_value=items
        ):
            rows, _ = parse_pdf(b"%PDF-1.4 fake", is_credit=True)
        by = {r.merchant: r.signed_amount for r in rows}
        assert by["COFFEE BAR"] == -8.56       # stays spend
        assert by["PAYMENT THANK YOU"] == 100.0  # stays credit

    def test_heuristic_path_still_flips_for_credit_accounts(self):
        text = "Opening/Closing Date 06/05/26 - 07/04/26\n06/06 SQ *COFFEE BAR 8.56\n"
        with patch("app.services.statement_pdf.extract_text", return_value=text):
            rows, _ = parse_pdf(b"%PDF-1.4 fake", is_credit=True)
        assert rows[0].signed_amount == -8.56
