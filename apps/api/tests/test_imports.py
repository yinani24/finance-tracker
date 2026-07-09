import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services.statement_import import (
    StatementParseError,
    _parse_amount,
    parse_csv,
)


@pytest.fixture(autouse=True)
def _tmp_import_storage(tmp_path):
    """Redirect statement uploads to a per-test tmp dir (no repo artifacts)."""
    original = settings.import_storage_dir
    settings.import_storage_dir = str(tmp_path / "imports")
    yield
    settings.import_storage_dir = original


def _make_account(client: TestClient, name: str = "Chase Checking") -> int:
    resp = client.post(
        "/accounts",
        json={"name": name, "type": "checking", "balance": 0, "currency": "USD"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _upload(client: TestClient, account_id: int, csv_text: str, filename="stmt.csv"):
    return client.post(
        "/imports",
        data={"account_id": str(account_id)},
        files={"file": (filename, csv_text.encode("utf-8"), "text/csv")},
    )


BASIC_CSV = (
    "Date,Description,Amount\n"
    "2026-06-01,STARBUCKS #123,-5.75\n"
    "2026-06-02,WHOLE FOODS,-42.10\n"
    "2026-06-03,PAYROLL DEPOSIT,2500.00\n"
)


class TestParseUnit:
    def test_parse_amount_variants(self):
        assert _parse_amount("-5.75") == -5.75
        assert _parse_amount("$1,234.56") == 1234.56
        assert _parse_amount("(50.00)") == -50.00
        assert _parse_amount(" 12.00 ") == 12.00

    def test_parse_amount_empty_raises(self):
        for bad in ("", "   ", "abc"):
            try:
                _parse_amount(bad)
                assert False, f"expected ValueError for {bad!r}"
            except ValueError:
                pass

    def test_parse_csv_header_variants(self):
        csv_text = (
            "Transaction Date,Merchant,Amount\n"
            "06/01/2026,Coffee Shop,-3.50\n"
        )
        rows, skipped = parse_csv(csv_text.encode("utf-8"))
        assert skipped == 0
        assert len(rows) == 1
        assert rows[0].merchant == "Coffee Shop"
        assert rows[0].signed_amount == -3.50
        assert rows[0].occurred_on.isoformat() == "2026-06-01"

    def test_parse_csv_skips_bad_rows(self):
        csv_text = (
            "Date,Description,Amount\n"
            "2026-06-01,Good,-1.00\n"
            "not-a-date,Bad Date,-2.00\n"
            "2026-06-03,Bad Amount,notnum\n"
        )
        rows, skipped = parse_csv(csv_text.encode("utf-8"))
        assert len(rows) == 1
        assert skipped == 2

    def test_parse_csv_missing_columns_raises(self):
        try:
            parse_csv(b"Foo,Bar\n1,2\n")
            assert False, "expected StatementParseError"
        except StatementParseError:
            pass

    def test_parse_csv_empty_raises(self):
        try:
            parse_csv(b"   ")
            assert False, "expected StatementParseError"
        except StatementParseError:
            pass


class TestImportAPI:
    def test_happy_path(self, client: TestClient):
        aid = _make_account(client)
        resp = _upload(client, aid, BASIC_CSV)
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "done"
        assert body["added"] == 3
        assert body["duplicates"] == 0
        assert body["skipped"] == 0
        assert body["total_rows"] == 3

        # Transactions landed under the account with the right sign convention.
        txns = client.get(f"/transactions?account_id={aid}").json()
        assert len(txns) == 3
        by_merchant = {t["merchant"]: t for t in txns}
        assert by_merchant["STARBUCKS #123"]["amount"] == -5.75
        assert by_merchant["STARBUCKS #123"]["is_income"] is False
        assert by_merchant["PAYROLL DEPOSIT"]["amount"] == 2500.00
        assert by_merchant["PAYROLL DEPOSIT"]["is_income"] is True
        # Enrichment (noop) normalizes the merchant.
        assert by_merchant["WHOLE FOODS"]["normalized_merchant"] == "whole foods"

    def test_get_import_status_and_count(self, client: TestClient):
        aid = _make_account(client)
        import_id = _upload(client, aid, BASIC_CSV).json()["import_id"]

        one = client.get(f"/imports/{import_id}")
        assert one.status_code == 200
        assert one.json()["status"] == "done"
        assert one.json()["transaction_count"] == 3

        listing = client.get("/imports").json()
        assert len(listing) == 1
        assert listing[0]["id"] == import_id

    def test_reupload_is_idempotent(self, client: TestClient):
        aid = _make_account(client)
        first = _upload(client, aid, BASIC_CSV).json()
        assert first["added"] == 3
        second = _upload(client, aid, BASIC_CSV).json()
        assert second["added"] == 0
        assert second["duplicates"] == 3
        # Still only 3 transactions total.
        assert len(client.get(f"/transactions?account_id={aid}").json()) == 3

    def test_bad_file_marks_failed_no_partial_rows(self, client: TestClient):
        aid = _make_account(client)
        resp = _upload(client, aid, "Foo,Bar\n1,2\n")
        assert resp.status_code == 400
        # No transactions were written.
        assert client.get(f"/transactions?account_id={aid}").json() == []
        # The import is recorded as failed.
        listing = client.get("/imports").json()
        assert len(listing) == 1
        assert listing[0]["status"] == "failed"
        assert listing[0]["transaction_count"] == 0

    def test_skipped_rows_counted(self, client: TestClient):
        aid = _make_account(client)
        csv_text = (
            "Date,Description,Amount\n"
            "2026-06-01,Good,-1.00\n"
            "bogus,Bad,-2.00\n"
        )
        body = _upload(client, aid, csv_text).json()
        assert body["added"] == 1
        assert body["skipped"] == 1
        assert body["total_rows"] == 2

    def test_import_into_unknown_account_404(self, client: TestClient):
        resp = _upload(client, 9999, BASIC_CSV)
        assert resp.status_code == 404

    def test_get_unknown_import_404(self, client: TestClient):
        assert client.get("/imports/9999").status_code == 404
