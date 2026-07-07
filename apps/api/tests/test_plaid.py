import json
from unittest.mock import MagicMock, patch

from plaid.exceptions import ApiException

from app.models.account import Account
from app.models.plaid_item import PlaidItem
from app.models.transaction import Transaction
from app.services.plaid_errors import map_plaid_exception
from app.services.plaid_service import _generate_dedupe_hash


def _plaid_api_exc(status: int, error_code: str) -> ApiException:
    """Build a Plaid ApiException whose body mirrors a real error payload.

    The body deliberately includes sensitive-looking fields (``error_message``,
    ``request_id``) so leak-prevention tests can assert they never surface.
    """
    exc = ApiException(status=status)
    exc.body = json.dumps(
        {
            "error_type": "ITEM_ERROR",
            "error_code": error_code,
            "error_message": "secret detail that must not leak",
            "request_id": "req_secret_x",
        }
    )
    return exc


class TestPlaidLinkToken:
    def test_create_link_token(self, client):
        mock_response = MagicMock()
        mock_response.link_token = "link-sandbox-abc123"
        mock_response.expiration = "2026-04-06T00:00:00Z"

        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.link_token_create.return_value = mock_response
            mock_get_client.return_value = mock_client

            resp = client.post("/plaid/link-token")
            assert resp.status_code == 200
            data = resp.json()
            assert data["link_token"] == "link-sandbox-abc123"
            assert data["expiration"] == "2026-04-06T00:00:00Z"


class TestPlaidExchangeToken:
    def test_exchange_token_creates_item(self, client, db_session):
        mock_exchange = MagicMock()
        mock_exchange.access_token = "access-sandbox-xyz"
        mock_exchange.item_id = "item-sandbox-123"

        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.item_public_token_exchange.return_value = mock_exchange
            mock_get_client.return_value = mock_client

            resp = client.post(
                "/plaid/exchange-token",
                json={
                    "public_token": "public-sandbox-abc",
                    "institution_id": "ins_1",
                    "institution_name": "Chase",
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["item_id"] == "item-sandbox-123"
            assert data["institution_name"] == "Chase"
            assert data["status"] == "active"

    def test_exchange_token_duplicate_rejected(self, client, db_session):
        db_session.add(
            PlaidItem(
                user_id=1,
                item_id="item-sandbox-123",
                access_token="access-sandbox-old",
            )
        )
        db_session.commit()

        mock_exchange = MagicMock()
        mock_exchange.access_token = "access-sandbox-new"
        mock_exchange.item_id = "item-sandbox-123"

        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.item_public_token_exchange.return_value = mock_exchange
            mock_get_client.return_value = mock_client

            resp = client.post(
                "/plaid/exchange-token",
                json={"public_token": "public-sandbox-abc"},
            )
            assert resp.status_code == 409


class TestPlaidItems:
    def test_list_items_empty(self, client):
        resp = client.get("/plaid/items")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_items_returns_items(self, client, db_session):
        db_session.add(
            PlaidItem(
                user_id=1,
                item_id="item-1",
                access_token="access-1",
                institution_name="Chase",
            )
        )
        db_session.commit()

        resp = client.get("/plaid/items")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["institution_name"] == "Chase"
        assert "access_token" not in items[0]

    def test_delete_item(self, client, db_session):
        item = PlaidItem(
            user_id=1,
            item_id="item-del",
            access_token="access-del",
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        resp = client.delete(f"/plaid/items/{item.id}")
        assert resp.status_code == 204

    def test_delete_item_not_found(self, client):
        resp = client.delete("/plaid/items/999")
        assert resp.status_code == 404


class TestPlaidSync:
    def _make_plaid_item(self, db_session) -> PlaidItem:
        item = PlaidItem(
            user_id=1,
            item_id="item-sync",
            access_token="access-sync",
            institution_name="Chase",
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item

    def _mock_sync_response(
        self, accounts=None, added=None, modified=None, removed=None, cursor="cursor-1"
    ):
        resp = MagicMock()
        resp.accounts = accounts or []
        resp.added = added or []
        resp.modified = modified or []
        resp.removed = removed or []
        resp.next_cursor = cursor
        resp.has_more = False
        return resp

    def _make_plaid_account(self, account_id="acct-1", name="Checking", acct_type="depository"):
        acct = MagicMock()
        acct.to_dict.return_value = {
            "account_id": account_id,
            "name": name,
            "type": acct_type,
            "balances": {"current": 1500.00},
        }
        return acct

    def _make_plaid_txn(
        self,
        txn_id="txn-1",
        account_id="acct-1",
        amount=25.50,
        merchant="Starbucks",
        date="2026-04-01",
    ):
        txn = MagicMock()
        txn.to_dict.return_value = {
            "transaction_id": txn_id,
            "account_id": account_id,
            "amount": amount,
            "merchant_name": merchant,
            "name": merchant,
            "date": date,
            "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
        }
        return txn

    def test_sync_creates_accounts_and_transactions(self, client, db_session):
        item = self._make_plaid_item(db_session)

        plaid_acct = self._make_plaid_account()
        plaid_txn = self._make_plaid_txn()
        mock_resp = self._mock_sync_response(
            accounts=[plaid_acct], added=[plaid_txn]
        )

        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.transactions_sync.return_value = mock_resp
            mock_get_client.return_value = mock_client

            resp = client.post(f"/plaid/items/{item.id}/sync")
            assert resp.status_code == 200
            data = resp.json()
            assert data["accounts_synced"] == 1
            assert data["transactions_added"] == 1
            assert data["transactions_modified"] == 0
            assert data["transactions_removed"] == 0

        accounts = db_session.query(Account).filter_by(user_id=1).all()
        assert len(accounts) == 1
        assert accounts[0].name == "Checking"
        assert accounts[0].balance == 1500.00

        txns = db_session.query(Transaction).filter_by(user_id=1).all()
        assert len(txns) == 1
        assert txns[0].merchant == "Starbucks"
        assert txns[0].amount == -25.50
        assert txns[0].source == "plaid"
        assert txns[0].is_income is False

    def test_sync_handles_modified_transactions(self, client, db_session):
        item = self._make_plaid_item(db_session)

        account = Account(
            user_id=1,
            name="Checking",
            type="checking",
            external_account_id="acct-1",
            balance=1000.0,
        )
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)

        db_session.add(
            Transaction(
                user_id=1,
                account_id=account.id,
                external_id="txn-mod",
                occurred_on="2026-04-01",
                amount=-25.50,
                merchant="Starbucks",
                dedupe_hash="abc123",
                source="plaid",
            )
        )
        db_session.commit()

        plaid_acct = self._make_plaid_account()
        modified_txn = MagicMock()
        modified_txn.to_dict.return_value = {
            "transaction_id": "txn-mod",
            "account_id": "acct-1",
            "amount": 30.00,
            "merchant_name": "Starbucks Reserve",
            "name": "Starbucks Reserve",
            "date": "2026-04-01",
        }

        mock_resp = self._mock_sync_response(
            accounts=[plaid_acct], modified=[modified_txn]
        )

        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.transactions_sync.return_value = mock_resp
            mock_get_client.return_value = mock_client

            resp = client.post(f"/plaid/items/{item.id}/sync")
            assert resp.status_code == 200
            assert resp.json()["transactions_modified"] == 1

        txn = db_session.query(Transaction).filter_by(external_id="txn-mod").first()
        assert txn.amount == -30.00
        assert txn.merchant == "Starbucks Reserve"

    def test_sync_handles_removed_transactions(self, client, db_session):
        item = self._make_plaid_item(db_session)

        account = Account(
            user_id=1,
            name="Checking",
            type="checking",
            external_account_id="acct-1",
            balance=1000.0,
        )
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)

        db_session.add(
            Transaction(
                user_id=1,
                account_id=account.id,
                external_id="txn-rem",
                occurred_on="2026-04-01",
                amount=-10.00,
                merchant="Test",
                dedupe_hash="xyz789",
                source="plaid",
            )
        )
        db_session.commit()

        plaid_acct = self._make_plaid_account()
        removed_txn = MagicMock()
        removed_txn.to_dict.return_value = {"transaction_id": "txn-rem"}

        mock_resp = self._mock_sync_response(
            accounts=[plaid_acct], removed=[removed_txn]
        )

        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.transactions_sync.return_value = mock_resp
            mock_get_client.return_value = mock_client

            resp = client.post(f"/plaid/items/{item.id}/sync")
            assert resp.status_code == 200
            assert resp.json()["transactions_removed"] == 1

        txn = db_session.query(Transaction).filter_by(external_id="txn-rem").first()
        assert txn is None

    def test_sync_item_not_found(self, client):
        resp = client.post("/plaid/items/999/sync")
        assert resp.status_code == 404

    def test_sync_deduplicates_transactions(self, client, db_session):
        item = self._make_plaid_item(db_session)

        plaid_acct = self._make_plaid_account()
        plaid_txn = self._make_plaid_txn()
        mock_resp = self._mock_sync_response(
            accounts=[plaid_acct], added=[plaid_txn]
        )

        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.transactions_sync.return_value = mock_resp
            mock_get_client.return_value = mock_client

            # First sync
            resp = client.post(f"/plaid/items/{item.id}/sync")
            assert resp.json()["transactions_added"] == 1

            # Second sync with same transaction — should deduplicate
            resp = client.post(f"/plaid/items/{item.id}/sync")
            assert resp.json()["transactions_added"] == 0

        txns = db_session.query(Transaction).filter_by(user_id=1).all()
        assert len(txns) == 1


class TestDedupeHash:
    def test_same_inputs_produce_same_hash(self):
        h1 = _generate_dedupe_hash("2026-04-01", 25.50, "Starbucks", 1)
        h2 = _generate_dedupe_hash("2026-04-01", 25.50, "Starbucks", 1)
        assert h1 == h2

    def test_different_inputs_produce_different_hash(self):
        h1 = _generate_dedupe_hash("2026-04-01", 25.50, "Starbucks", 1)
        h2 = _generate_dedupe_hash("2026-04-02", 25.50, "Starbucks", 1)
        assert h1 != h2

    def test_hash_is_16_chars(self):
        h = _generate_dedupe_hash("2026-04-01", 25.50, "Starbucks", 1)
        assert len(h) == 16


class TestMapPlaidException:
    """Unit tests for the pure classifier (no DB / HTTP)."""

    def test_relink_codes_map_to_409(self):
        for code in (
            "ITEM_LOGIN_REQUIRED",
            "INVALID_ACCESS_TOKEN",
            "INVALID_CREDENTIALS",
            "ITEM_NOT_FOUND",
            "ACCESS_NOT_GRANTED",
        ):
            err = map_plaid_exception(_plaid_api_exc(400, code))
            assert err.http_status == 409
            assert err.error_code == code
            assert err.action == "relink"

    def test_rate_limit_maps_to_503_retry(self):
        err = map_plaid_exception(_plaid_api_exc(429, "RATE_LIMIT_EXCEEDED"))
        assert err.http_status == 503
        assert err.action == "retry"

    def test_plaid_5xx_maps_to_503_even_for_unknown_code(self):
        err = map_plaid_exception(_plaid_api_exc(503, "SOMETHING_WEIRD"))
        assert err.http_status == 503
        assert err.action == "retry"

    def test_generic_error_maps_to_502_without_action(self):
        err = map_plaid_exception(_plaid_api_exc(400, "INVALID_FIELD"))
        assert err.http_status == 502
        assert err.error_code == "INVALID_FIELD"
        assert err.action is None

    def test_non_json_body_falls_back_to_unknown_502(self):
        exc = ApiException(status=400)
        exc.body = "<html>gateway error</html>"
        err = map_plaid_exception(exc)
        assert err.http_status == 502
        assert err.error_code == "UNKNOWN"

    def test_missing_body_falls_back_to_unknown_502(self):
        exc = ApiException(status=400)
        exc.body = None
        err = map_plaid_exception(exc)
        assert err.http_status == 502
        assert err.error_code == "UNKNOWN"


class TestPlaidErrorHTTPMapping:
    """Integration tests: PlaidError raised in the service is rendered by the
    registered exception handler into a sanitized HTTP response."""

    def _make_plaid_item(self, db_session) -> PlaidItem:
        item = PlaidItem(
            user_id=1,
            item_id="item-err",
            access_token="access-should-never-leak",
            institution_name="Chase",
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item

    def test_item_login_required_returns_409_relink(self, client, db_session):
        item = self._make_plaid_item(db_session)
        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.transactions_sync.side_effect = _plaid_api_exc(
                400, "ITEM_LOGIN_REQUIRED"
            )
            mock_get_client.return_value = mock_client

            resp = client.post(f"/plaid/items/{item.id}/sync")

        assert resp.status_code == 409
        assert resp.json() == {
            "error_code": "ITEM_LOGIN_REQUIRED",
            "action": "relink",
        }

    def test_rate_limit_returns_503_retry(self, client, db_session):
        item = self._make_plaid_item(db_session)
        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.transactions_sync.side_effect = _plaid_api_exc(
                429, "RATE_LIMIT_EXCEEDED"
            )
            mock_get_client.return_value = mock_client

            resp = client.post(f"/plaid/items/{item.id}/sync")

        assert resp.status_code == 503
        assert resp.json() == {
            "error_code": "RATE_LIMIT_EXCEEDED",
            "action": "retry",
        }

    def test_generic_error_returns_502_no_action(self, client):
        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.link_token_create.side_effect = _plaid_api_exc(
                400, "INVALID_FIELD"
            )
            mock_get_client.return_value = mock_client

            resp = client.post("/plaid/link-token")

        assert resp.status_code == 502
        assert resp.json() == {"error_code": "INVALID_FIELD"}

    def test_non_json_body_returns_502_unknown(self, client):
        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            exc = ApiException(status=400)
            exc.body = None
            mock_client.link_token_create.side_effect = exc
            mock_get_client.return_value = mock_client

            resp = client.post("/plaid/link-token")

        assert resp.status_code == 502
        assert resp.json() == {"error_code": "UNKNOWN"}

    def test_error_response_never_leaks_secrets(self, client, db_session):
        item = self._make_plaid_item(db_session)
        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.transactions_sync.side_effect = _plaid_api_exc(
                400, "ITEM_LOGIN_REQUIRED"
            )
            mock_get_client.return_value = mock_client

            resp = client.post(f"/plaid/items/{item.id}/sync")

        assert "secret detail that must not leak" not in resp.text
        assert "req_secret_x" not in resp.text
        assert "access-should-never-leak" not in resp.text
