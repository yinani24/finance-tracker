import hashlib
import json
import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.config import settings
from app.models.account import Account
from app.models.plaid_item import PlaidItem
from app.models.transaction import Transaction
from app.services import plaid_webhook


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
    @pytest.fixture(autouse=True)
    def _disable_verification(self, monkeypatch):
        """These functional tests POST unsigned bodies; verification is
        exercised separately in ``TestWebhookVerification``."""
        monkeypatch.setattr(settings, "plaid_webhook_verify", False)

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


def _mint_keypair(kid="test_kid"):
    priv = ec.generate_private_key(ec.SECP256R1())
    alg = jwt.algorithms.ECAlgorithm(jwt.algorithms.ECAlgorithm.SHA256)
    pub_jwk = json.loads(alg.to_jwk(priv.public_key()))
    pub_jwk.update({"kid": kid, "use": "sig", "alg": "ES256"})
    return priv, pub_jwk


def _sign(priv, body: bytes, iat=None, kid="test_kid", alg="ES256"):
    claims = {
        "iat": int(iat if iat is not None else time.time()),
        "request_body_sha256": hashlib.sha256(body).hexdigest(),
    }
    return jwt.encode(claims, priv, algorithm=alg, headers={"kid": kid})


class TestWebhookVerification:
    """Exercises the real Plaid-Verification JWT check (flag enabled)."""

    @pytest.fixture(autouse=True)
    def _enable_and_isolate(self, monkeypatch):
        monkeypatch.setattr(settings, "plaid_webhook_verify", True)
        plaid_webhook._KEY_CACHE.clear()
        yield
        plaid_webhook._KEY_CACHE.clear()

    @staticmethod
    def _mock_key_client(pub_jwk):
        """Patch the key-fetch client used inside verify_webhook."""
        mock_client = MagicMock()
        mock_client.webhook_verification_key_get.return_value.key.to_dict.return_value = (
            pub_jwk
        )
        return patch(
            "app.services.plaid_webhook.get_plaid_client", return_value=mock_client
        ), mock_client

    def _post(self, client, body, token):
        headers = {"content-type": "application/json"}
        if token is not None:
            headers["Plaid-Verification"] = token
        return client.post("/plaid/webhook", content=body, headers=headers)

    def test_valid_signature_accepted_and_syncs(self, client, db_session):
        item = _make_plaid_item(db_session)
        priv, pub_jwk = _mint_keypair()
        body = json.dumps(_sync_payload(item.item_id)).encode()
        token = _sign(priv, body)
        key_patch, _ = self._mock_key_client(pub_jwk)

        mock_resp = _mock_sync_response(
            accounts=[_make_plaid_account()], added=[_make_plaid_txn()]
        )
        with key_patch, patch("app.api.plaid.get_plaid_client") as mock_get_client, patch(
            "app.api.plaid.fire_insights_event"
        ):
            mock_client = MagicMock()
            mock_client.transactions_sync.return_value = mock_resp
            mock_get_client.return_value = mock_client

            resp = self._post(client, body, token)

        assert resp.status_code == 200
        assert resp.json()["status"] == "synced"

    def test_missing_header_rejected(self, client, db_session):
        _make_plaid_item(db_session)
        body = json.dumps(_sync_payload()).encode()
        resp = self._post(client, body, token=None)
        assert resp.status_code == 401

    def test_tampered_body_rejected(self, client, db_session):
        _make_plaid_item(db_session)
        priv, pub_jwk = _mint_keypair()
        signed_body = json.dumps(_sync_payload()).encode()
        token = _sign(priv, signed_body)
        key_patch, _ = self._mock_key_client(pub_jwk)

        # Sign one body but send a different one → hash claim mismatch.
        tampered = signed_body + b" "
        with key_patch:
            resp = self._post(client, tampered, token)
        assert resp.status_code == 401

    def test_bad_signature_rejected(self, client, db_session):
        _make_plaid_item(db_session)
        # Sign with one key, verify against a different (unrelated) key.
        signing_priv, _ = _mint_keypair()
        _, other_pub_jwk = _mint_keypair()
        body = json.dumps(_sync_payload()).encode()
        token = _sign(signing_priv, body)
        key_patch, _ = self._mock_key_client(other_pub_jwk)

        with key_patch:
            resp = self._post(client, body, token)
        assert resp.status_code == 401

    def test_stale_iat_rejected(self, client, db_session):
        _make_plaid_item(db_session)
        priv, pub_jwk = _mint_keypair()
        body = json.dumps(_sync_payload()).encode()
        token = _sign(priv, body, iat=time.time() - 600)  # 10 min old
        key_patch, _ = self._mock_key_client(pub_jwk)

        with key_patch:
            resp = self._post(client, body, token)
        assert resp.status_code == 401

    def test_wrong_alg_rejected(self, client, db_session):
        """A token signed with HS256 must be rejected (alg-confusion guard)."""
        _make_plaid_item(db_session)
        _, pub_jwk = _mint_keypair()
        body = json.dumps(_sync_payload()).encode()
        hs_token = jwt.encode(
            {
                "iat": int(time.time()),
                "request_body_sha256": hashlib.sha256(body).hexdigest(),
            },
            "shared-secret",
            algorithm="HS256",
            headers={"kid": "test_kid"},
        )
        key_patch, _ = self._mock_key_client(pub_jwk)

        with key_patch:
            resp = self._post(client, body, hs_token)
        assert resp.status_code == 401

    def test_key_cached_by_kid(self, client, db_session):
        _make_plaid_item(db_session)
        priv, pub_jwk = _mint_keypair()
        key_patch, mock_client = self._mock_key_client(pub_jwk)

        with key_patch, patch("app.api.plaid.get_plaid_client") as mock_get_client, patch(
            "app.api.plaid.fire_insights_event"
        ):
            mock_get_client.return_value.transactions_sync.return_value = (
                _mock_sync_response()
            )
            for _ in range(2):
                body = json.dumps(_sync_payload()).encode()
                token = _sign(priv, body)
                resp = self._post(client, body, token)
                assert resp.status_code == 200

        # Two webhooks with the same kid → key fetched exactly once.
        assert mock_client.webhook_verification_key_get.call_count == 1

    def test_disabled_flag_skips_verification(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "plaid_webhook_verify", False)
        _make_plaid_item(db_session)
        body = json.dumps(_sync_payload()).encode()
        with patch("app.api.plaid.get_plaid_client") as mock_get_client, patch(
            "app.api.plaid.fire_insights_event"
        ):
            mock_get_client.return_value.transactions_sync.return_value = (
                _mock_sync_response()
            )
            # No Plaid-Verification header at all, yet accepted.
            resp = self._post(client, body, token=None)
        assert resp.status_code == 200
        assert resp.json()["status"] == "synced"
