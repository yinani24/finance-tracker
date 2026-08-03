from unittest.mock import MagicMock, patch

from app.models.plaid_item import PlaidItem
from app.models.transaction import Transaction
from app.services.enrichment import (
    EnrichmentInput,
    EnrichmentResult,
    NoopProvider,
    RulesProvider,
    get_provider,
)
from app.services.enrichment.taxonomy import (
    INTERNAL_CATEGORIES,
    map_to_internal,
)


class TestProviderFactory:
    def test_default_is_rules(self):
        # Default is the rule-based categorizer so statement-import data (which
        # arrives with no category) still gets a spending breakdown.
        assert isinstance(get_provider(), RulesProvider)

    def test_explicit_noop(self):
        assert isinstance(get_provider("noop"), NoopProvider)

    def test_explicit_rules(self):
        assert isinstance(get_provider("rules"), RulesProvider)

    def test_unknown_falls_back_to_noop(self):
        # A bad/misconfigured provider name must never break ingest.
        assert isinstance(get_provider("does-not-exist"), NoopProvider)


class TestNoopProvider:
    def test_maps_raw_category_to_internal_taxonomy(self):
        # Per the provider contract, `category` must be in our internal taxonomy,
        # not the raw vendor label. The raw label is preserved separately.
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
        assert results[0].category == "dining"
        assert results[0].raw_provider_category == "food and drink"
        assert results[0].normalized_merchant == "starbucks"
        assert results[0].confidence is None

    def test_none_category_passes_through_as_none(self):
        # A missing upstream category must stay None (NOT map to "other") so
        # apply_enrichment leaves the row untouched — the statement-import path
        # (plaid_category=None, category derived elsewhere) depends on this.
        provider = NoopProvider()
        results = provider.enrich(
            [EnrichmentInput(merchant="Corner Store", amount=-12.0, plaid_category=None)]
        )
        assert results[0].category is None
        assert results[0].raw_provider_category is None
        assert results[0].normalized_merchant == "corner store"

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

    def test_plaid_detailed_food_split(self):
        # Plaid's primary FOOD_AND_DRINK conflates groceries with dining; the
        # detailed label separates them so category_breakdown's grocery bucket
        # fills and the dining share isn't inflated.
        assert map_to_internal("FOOD_AND_DRINK_GROCERIES") == "groceries"
        assert map_to_internal("FOOD_AND_DRINK_RESTAURANT") == "dining"
        assert map_to_internal("FOOD_AND_DRINK_COFFEE") == "dining"
        assert map_to_internal("FOOD_AND_DRINK_FAST_FOOD") == "dining"
        assert map_to_internal("FOOD_AND_DRINK_BEER_WINE_AND_LIQUOR") == "dining"
        assert map_to_internal("FOOD_AND_DRINK_VENDING_MACHINES") == "dining"
        assert map_to_internal("FOOD_AND_DRINK_OTHER") == "dining"

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
            "app.services.enrichment.apply.get_provider", return_value=_FakeProvider()
        ):
            resp = self._run_sync(client)
        assert resp.status_code == 200
        assert resp.json()["transactions_added"] == 1

        txn = db_session.query(Transaction).filter_by(user_id=1).one()
        assert txn.category == "dining"
        assert txn.normalized_merchant == "STARBUCKS_CLEAN"
        # Provenance is stamped when the provider assigns a category.
        assert txn.category_confidence == 0.99
        assert txn.enriched_at is not None

    def test_fail_open_leaves_provenance_unstamped(self, client, db_session):
        # A provider blow-up must not stamp confidence/enriched_at, so the row
        # stays a backfill candidate (enriched_at IS NULL).
        self._item_id = self._make_plaid_item(db_session).id
        with patch(
            "app.services.enrichment.apply.get_provider", return_value=_BoomProvider()
        ):
            resp = self._run_sync(client)
        assert resp.status_code == 200

        txn = db_session.query(Transaction).filter_by(user_id=1).one()
        assert txn.category_confidence is None
        assert txn.enriched_at is None

    def test_fail_open_keeps_raw_category(self, client, db_session):
        self._item_id = self._make_plaid_item(db_session).id
        with patch(
            "app.services.enrichment.apply.get_provider", return_value=_BoomProvider()
        ):
            resp = self._run_sync(client)
        # Provider blew up, but ingest must still succeed with raw Plaid values.
        assert resp.status_code == 200
        assert resp.json()["transactions_added"] == 1

        txn = db_session.query(Transaction).filter_by(user_id=1).one()
        assert txn.category == "food and drink"
        assert txn.normalized_merchant == "starbucks"

    def test_default_noop_maps_to_internal_taxonomy(self, client, db_session):
        # No provider patch → default noop → the raw Plaid label FOOD_AND_DRINK
        # is mapped into our internal taxonomy ("dining"), so category_breakdown
        # stays vendor-agnostic and the recommendation engine sees "dining".
        self._item_id = self._make_plaid_item(db_session).id
        resp = self._run_sync(client)
        assert resp.status_code == 200

        txn = db_session.query(Transaction).filter_by(user_id=1).one()
        assert txn.category == "dining"
        assert txn.normalized_merchant == "starbucks"

    def _make_pfc_txn(self, txn_id, merchant, pfc):
        txn = MagicMock()
        txn.to_dict.return_value = {
            "transaction_id": txn_id,
            "account_id": "acct-1",
            "amount": 25.5,
            "merchant_name": merchant,
            "name": merchant,
            "date": "2026-04-01",
            "personal_finance_category": pfc,
        }
        return txn

    def _run_sync_with(self, client, added):
        mock_resp = self._mock_sync_response(
            accounts=[self._make_plaid_account()], added=added
        )
        with patch("app.api.plaid.get_plaid_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.transactions_sync.return_value = mock_resp
            mock_get_client.return_value = mock_client
            return client.post(f"/plaid/items/{self._item_id}/sync")

    def test_detailed_splits_groceries_from_dining_at_ingest(
        self, client, db_session
    ):
        # The whole point of #52: a grocery run and a restaurant charge both
        # arrive under Plaid's primary FOOD_AND_DRINK, but the detailed label
        # must land them in distinct internal buckets so the dining share the
        # recommender ranks on isn't inflated by grocery spend.
        self._item_id = self._make_plaid_item(db_session).id
        resp = self._run_sync_with(
            client,
            [
                self._make_pfc_txn(
                    "txn-groc",
                    "Whole Foods",
                    {
                        "primary": "FOOD_AND_DRINK",
                        "detailed": "FOOD_AND_DRINK_GROCERIES",
                    },
                ),
                self._make_pfc_txn(
                    "txn-rest",
                    "Chipotle",
                    {
                        "primary": "FOOD_AND_DRINK",
                        "detailed": "FOOD_AND_DRINK_RESTAURANT",
                    },
                ),
            ],
        )
        assert resp.status_code == 200

        cats = {
            t.merchant: t.category
            for t in db_session.query(Transaction).filter_by(user_id=1).all()
        }
        assert cats["Whole Foods"] == "groceries"
        assert cats["Chipotle"] == "dining"

    def test_missing_detailed_falls_back_to_primary(self, client, db_session):
        # Older/partial data with no detailed label must not regress — it keeps
        # mapping via the primary category (FOOD_AND_DRINK → dining).
        self._item_id = self._make_plaid_item(db_session).id
        resp = self._run_sync_with(
            client,
            [
                self._make_pfc_txn(
                    "txn-noDetail",
                    "Starbucks",
                    {"primary": "FOOD_AND_DRINK"},
                )
            ],
        )
        assert resp.status_code == 200

        txn = db_session.query(Transaction).filter_by(user_id=1).one()
        assert txn.category == "dining"

    def test_non_food_primary_ignores_detailed(self, client, db_session):
        # Only FOOD_AND_DRINK is conflated. Other primaries keep using the
        # primary label (their detailed labels aren't in the taxonomy and would
        # wrongly collapse to "other"), so transport stays transport.
        self._item_id = self._make_plaid_item(db_session).id
        resp = self._run_sync_with(
            client,
            [
                self._make_pfc_txn(
                    "txn-gas",
                    "Shell",
                    {
                        "primary": "TRANSPORTATION",
                        "detailed": "TRANSPORTATION_GAS",
                    },
                )
            ],
        )
        assert resp.status_code == 200

        txn = db_session.query(Transaction).filter_by(user_id=1).one()
        assert txn.category == "transport"


class TestRulesProvider:
    def _cat(self, merchant, plaid_category=None):
        (res,) = RulesProvider().enrich(
            [EnrichmentInput(merchant=merchant, amount=-10.0, plaid_category=plaid_category)]
        )
        return res.category

    def test_categorizes_common_merchants_by_name(self):
        cases = {
            "STARBUCKS #1122": "dining",
            "DOORDASH SUSHI": "dining",
            "WHOLE FOODS MKT": "groceries",   # must NOT be dining
            "TRADER JOES": "groceries",
            "DELTA AIR LINES": "travel",
            "MARRIOTT HOTEL": "travel",
            "UBER TRIP": "transport",
            "AMAZON MKTPL": "shopping",
            "RENT PAYMENT": "bills",
            "PG&E ELECTRIC": "bills",
        }
        for merchant, expected in cases.items():
            assert self._cat(merchant) == expected, merchant

    def test_unknown_merchant_falls_back_to_other(self):
        assert self._cat("ZZZ QRSTUV LLC") == "other"

    def test_prefers_upstream_plaid_category_when_present(self):
        # Plaid-sourced rows keep their upstream category (mapped to our
        # taxonomy); merchant rules only fill in when there is none.
        assert self._cat("STARBUCKS #1122", plaid_category="travel") == "travel"


class TestProcessorAndBoundaryRules:
    def _cat(self, merchant):
        (r,) = RulesProvider().enrich(
            [EnrichmentInput(merchant=merchant, amount=-10.0)]
        )
        return r.category

    def test_processor_prefix_rescues_unknown_merchant(self):
        # We've never heard of these restaurants, but the processor tells us.
        assert self._cat("TST* CHONG QING XIAO MIAN San Francisco CA") == "dining"
        assert self._cat("SQ *THE NOSH BOX San Francisco CA") == "dining"
        assert self._cat("IC* COSTCO BY INSTACART") == "groceries"
        assert self._cat("BAYWHEE*2 RIDES HELP.LYFT.COM CA") == "transport"

    def test_known_merchant_keyword_beats_processor(self):
        # DD* is dining, but an explicit keyword still decides first.
        assert self._cat("DD *DOORDASH APPLEBEES 855-431-0459 CA") == "dining"

    def test_word_boundary_prevents_substring_false_positive(self):
        # "mobil" (the gas brand) must NOT match "...-Mobile", which had been
        # filing credit-card payments under transport.
        assert self._cat("Payment Thank You-Mobile") != "transport"

    def test_prefix_keyword_matches_name_run_onto_digits(self):
        assert self._cat("AMERICAN AIR0011111111111 FORT WORTH TX") == "travel"

    def test_unknown_still_falls_back_to_other(self):
        assert self._cat("ZZZQQ HOLDINGS LLC") == "other"
