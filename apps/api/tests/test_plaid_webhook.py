from unittest.mock import MagicMock, patch

from app.models.account import Account
from app.models.plaid_item import PlaidItem
from app.models.transaction import Transaction


def _make_plaid_item(db_session, item_id="item-webhook", user_id=1) -> PlaidItem:
    item = PlaidItem(
        user_id=user_id,
        item_id=item_id,
        access_token="access-webhook",
        institution_name="Chase",
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def _mock_sync_response(accounts=None, added=None, cursor="cursor-1"):
    resp = MagicMock()
    resp.accounts = accounts or []
    resp.added = added or []
    resp.modified = []
    resp.removed = []
    resp.next_cursor = cursor
    resp.has_more = False
    return resp


def _make_plaid_account(account_id="acct-1", name="Checking", acct_type="depository"):
    acct = MagicMock()
    acct.to_dict.return_value = {
        "account_id": account_id,
        "name": name,
        "type": acct_type,
        "balances": {"current": 1500.00},
    }
    return acct


def _make_plaid_txn(txn_id="txn-1", account_id="acct-1", amount=25.50, merchant="Starbucks"):
    txn = MagicMock()
    txn.to_dict.return_value = {
        "transaction_id": txn_id,
        "account_id": account_id,
        "amount": amount,
        "merchant_name": merchant,
        "name": merchant,
        "date": "2026-04-01",
        "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
    }
    return txn


def _sync_payload(item_id="item-webhook"):
    return {
        "webhook_type": "TRANSACTIONS",
        "webhook_code": "SYNC_UPDATES_AVAILABLE",
        "item_id": item_id,
        "environment": "sandbox",
    }


class TestPlaidWebhookSync:
    def test_sync_updates_available_triggers_sync(self, client, db_session):
        item = _make_plaid_item(db_session)
        mock_resp = _mock_sync_response(
            accounts=[_make_plaid_account()], added=[_make_plaid_txn()]
        )

        with patch("app.api.plaid.get_plaid_client") as mock_get_client, patch(
            "app.api.plaid.fire_insights_event"
        ) as mock_fire:
            mock_client = MagicMock()
            mock_client.transactions_sync.return_value = mock_resp
            mock_get_client.return_value = mock_client

            resp = client.post("/plaid/webhook", json=_sync_payload(item.item_id))

            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "synced"
            assert data["transactions_added"] == 1
            assert data["accounts_synced"] == 1
            # Insights event fired, keyed on the item's user_id (webhook has no session).
            mock_fire.assert_called_once()
            assert mock_fire.call_args[0][2] == item.user_id

        accounts = db_session.query(Account).filter_by(user_id=1).all()
        assert len(accounts) == 1
        txns = db_session.query(Transaction).filter_by(user_id=1).all()
        assert len(txns) == 1
        assert txns[0].merchant == "Starbucks"

    def test_idempotent_replay_does_not_duplicate(self, client, db_session):
        item = _make_plaid_item(db_session)
        mock_resp = _mock_sync_response(
            accounts=[_make_plaid_account()], added=[_make_plaid_txn()]
        )

        with patch("app.api.plaid.get_plaid_client") as mock_get_client, patch(
            "app.api.plaid.fire_insights_event"
        ):
            mock_client = MagicMock()
            mock_client.transactions_sync.return_value = mock_resp
            mock_get_client.return_value = mock_client

            first = client.post("/plaid/webhook", json=_sync_payload(item.item_id))
            assert first.json()["transactions_added"] == 1

            second = client.post("/plaid/webhook", json=_sync_payload(item.item_id))
            assert second.status_code == 200
            assert second.json()["transactions_added"] == 0

        txns = db_session.query(Transaction).filter_by(user_id=1).all()
        assert len(txns) == 1

    def test_unknown_item_id_is_noop(self, client, db_session):
        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            resp = client.post("/plaid/webhook", json=_sync_payload("item-does-not-exist"))
            assert resp.status_code == 200
            assert resp.json()["reason"] == "unknown_item"
            # No Plaid call attempted for an unknown item.
            mock_get_client.assert_not_called()

        assert db_session.query(Transaction).count() == 0

    def test_unhandled_webhook_type_is_noop(self, client, db_session):
        _make_plaid_item(db_session)
        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            resp = client.post(
                "/plaid/webhook",
                json={"webhook_type": "ITEM", "webhook_code": "ERROR", "item_id": "item-webhook"},
            )
            assert resp.status_code == 200
            assert resp.json()["reason"] == "unhandled_webhook"
            mock_get_client.assert_not_called()

    def test_unparseable_body_is_noop(self, client):
        resp = client.post(
            "/plaid/webhook",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.json()["reason"] == "unparseable"

    def test_sync_error_still_returns_200(self, client, db_session):
        """A failing sync must not 5xx — Plaid retries non-2xx, so we swallow."""
        item = _make_plaid_item(db_session)

        with patch("app.api.plaid.get_plaid_client") as mock_get_client, patch(
            "app.api.plaid.fire_insights_event"
        ) as mock_fire:
            mock_client = MagicMock()
            mock_client.transactions_sync.side_effect = RuntimeError("boom")
            mock_get_client.return_value = mock_client

            resp = client.post("/plaid/webhook", json=_sync_payload(item.item_id))
            assert resp.status_code == 200
            assert resp.json()["status"] == "error"
            mock_fire.assert_not_called()

    def test_failed_verification_returns_401(self, client, db_session):
        _make_plaid_item(db_session)
        with patch("app.api.plaid.verify_webhook", return_value=False):
            resp = client.post("/plaid/webhook", json=_sync_payload("item-webhook"))
            assert resp.status_code == 401


class TestWebhookUrlThreadedIntoLinkToken:
    def test_webhook_url_threaded_when_set(self, client, monkeypatch):
        monkeypatch.setattr(
            "app.services.plaid_service.settings.plaid_webhook_url",
            "https://example.com/plaid/webhook",
        )
        mock_response = MagicMock()
        mock_response.link_token = "link-sandbox-abc123"
        mock_response.expiration = "2026-04-06T00:00:00Z"

        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.link_token_create.return_value = mock_response
            mock_get_client.return_value = mock_client

            resp = client.post("/plaid/link-token")
            assert resp.status_code == 200

        sent_request = mock_client.link_token_create.call_args[0][0]
        assert sent_request.to_dict()["webhook"] == "https://example.com/plaid/webhook"

    def test_webhook_url_absent_when_unset(self, client):
        mock_response = MagicMock()
        mock_response.link_token = "link-sandbox-abc123"
        mock_response.expiration = "2026-04-06T00:00:00Z"

        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.link_token_create.return_value = mock_response
            mock_get_client.return_value = mock_client

            resp = client.post("/plaid/link-token")
            assert resp.status_code == 200

        sent_request = mock_client.link_token_create.call_args[0][0]
        assert "webhook" not in sent_request.to_dict()
