from unittest.mock import MagicMock, patch

from app.models.plaid_item import PlaidItem
from app.models.transaction import Transaction
from app.services.enrichment import (
    EnrichmentInput,
    EnrichmentResult,
    NoopProvider,
    get_provider,
)
from app.services.enrichment.taxonomy import (
    INTERNAL_CATEGORIES,
    map_to_internal,
)


class TestProviderFactory:
    def test_default_is_noop(self):
        assert isinstance(get_provider(), NoopProvider)

    def test_explicit_noop(self):
        assert isinstance(get_provider("noop"), NoopProvider)

    def test_unknown_falls_back_to_noop(self):
        # A bad/misconfigured provider name must never break ingest.
        assert isinstance(get_provider("does-not-exist"), NoopProvider)


class TestNoopProvider:
    def test_passthrough_preserves_category(self):
        provider = NoopProvider()
        results = provider.enrich(
            [
                EnrichmentInput(
                    external_id="t1",
                    merchant="Starbucks",
                    amount=-4.5,
                    plaid_category="food and drink",
                )
            ]
        )
        assert len(results) == 1
        assert results[0].category == "food and drink"
        assert results[0].normalized_merchant == "starbucks"
        assert results[0].confidence is None

    def test_empty_batch(self):
        assert NoopProvider().enrich([]) == []


class TestTaxonomyMapper:
    def test_known_plaid_labels_map(self):
        assert map_to_internal("food and drink") == "dining"
        assert map_to_internal("FOOD_AND_DRINK") == "dining"
        assert map_to_internal("general merchandise") == "shopping"
        assert map_to_internal("transportation") == "transport"
        assert map_to_internal("rent and utilities") == "bills"
        assert map_to_internal("medical") == "health"
        assert map_to_internal("income") == "income"

    def test_vendor_synonyms_map(self):
        assert map_to_internal("Restaurants") == "dining"
        assert map_to_internal("groceries") == "groceries"
        assert map_to_internal("Food & Drink") == "dining"

    def test_unknown_and_empty_go_to_other(self):
        assert map_to_internal("cryptocurrency mining") == "other"
        assert map_to_internal("") == "other"
        assert map_to_internal(None) == "other"

    def test_every_mapped_value_is_in_the_internal_set(self):
        for label in ["food and drink", "income", "transfer in", "gas", "streaming"]:
            assert map_to_internal(label) in INTERNAL_CATEGORIES


class _FakeProvider:
    """Overwrites every txn with a fixed dining classification."""

    def enrich(self, txns):
        return [
            EnrichmentResult(
                normalized_merchant="STARBUCKS_CLEAN",
                category="dining",
                confidence=0.99,
            )
            for _ in txns
        ]


class _BoomProvider:
    def enrich(self, txns):
        raise RuntimeError("provider is down")


class TestSyncEnrichmentHook:
    def _make_plaid_item(self, db_session) -> PlaidItem:
        item = PlaidItem(
            user_id=1,
            item_id="item-enrich",
            access_token="access-enrich",
            institution_name="Chase",
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item

    def _mock_sync_response(self, accounts, added):
        resp = MagicMock()
        resp.accounts = accounts
        resp.added = added
        resp.modified = []
        resp.removed = []
        resp.next_cursor = "cursor-1"
        resp.has_more = False
        return resp

    def _make_plaid_account(self):
        acct = MagicMock()
        acct.to_dict.return_value = {
            "account_id": "acct-1",
            "name": "Checking",
            "type": "depository",
            "balances": {"current": 1500.0},
        }
        return acct

    def _make_plaid_txn(self):
        txn = MagicMock()
        txn.to_dict.return_value = {
            "transaction_id": "txn-1",
            "account_id": "acct-1",
            "amount": 25.5,
            "merchant_name": "Starbucks",
            "name": "Starbucks",
            "date": "2026-04-01",
            "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
        }
        return txn

    def _run_sync(self, client):
        mock_resp = self._mock_sync_response(
            accounts=[self._make_plaid_account()], added=[self._make_plaid_txn()]
        )
        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.transactions_sync.return_value = mock_resp
            mock_get_client.return_value = mock_client
            resp = client.post(f"/plaid/items/{self._item_id}/sync")
        return resp

    def test_provider_overwrites_category_and_merchant(self, client, db_session):
        self._item_id = self._make_plaid_item(db_session).id
        with patch(
            "app.services.plaid_service.get_provider", return_value=_FakeProvider()
        ):
            resp = self._run_sync(client)
        assert resp.status_code == 200
        assert resp.json()["transactions_added"] == 1

        txn = db_session.query(Transaction).filter_by(user_id=1).one()
        assert txn.category == "dining"
        assert txn.normalized_merchant == "STARBUCKS_CLEAN"

    def test_fail_open_keeps_raw_category(self, client, db_session):
        self._item_id = self._make_plaid_item(db_session).id
        with patch(
            "app.services.plaid_service.get_provider", return_value=_BoomProvider()
        ):
            resp = self._run_sync(client)
        # Provider blew up, but ingest must still succeed with raw Plaid values.
        assert resp.status_code == 200
        assert resp.json()["transactions_added"] == 1

        txn = db_session.query(Transaction).filter_by(user_id=1).one()
        assert txn.category == "food and drink"
        assert txn.normalized_merchant == "starbucks"

    def test_default_noop_is_behavior_preserving(self, client, db_session):
        # No provider patch → default noop → identical to pre-enrichment behavior.
        self._item_id = self._make_plaid_item(db_session).id
        resp = self._run_sync(client)
        assert resp.status_code == 200

        txn = db_session.query(Transaction).filter_by(user_id=1).one()
        assert txn.category == "food and drink"
        assert txn.normalized_merchant == "starbucks"
