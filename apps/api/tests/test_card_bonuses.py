"""Tests for the card-bonuses service and API router.

The service functions are async; tests drive them with ``asyncio.run`` to avoid
adding a pytest-asyncio dependency.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services import card_bonuses

SAMPLE_CARDS = [
    {
        "cardId": "amex-blue",
        "name": "Delta SkyMiles Blue",
        "issuer": "AMERICAN_EXPRESS",
        "network": "AMERICAN_EXPRESS",
        "isBusiness": False,
        "annualFee": 0,
        "url": "https://amex.example/blue",
    },
    {
        "cardId": "chase-sapphire",
        "name": "Chase Sapphire Preferred",
        "issuer": "CHASE",
        "network": "VISA",
        "isBusiness": False,
        "annualFee": 95,
        "url": "https://chase.example/sapphire",
    },
    {
        "cardId": "chase-ink",
        "name": "Ink Business Preferred",
        "issuer": "CHASE",
        "network": "MASTERCARD",
        "isBusiness": True,
        "annualFee": 95,
        "url": "https://chase.example/ink",
    },
]


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clear_cache():
    card_bonuses.clear_cache()
    yield
    card_bonuses.clear_cache()


def _patch_fetch(cards=SAMPLE_CARDS):
    return patch.object(card_bonuses, "_fetch_cards", AsyncMock(return_value=cards))


class TestSearchCards:
    def test_returns_all_by_default(self):
        with _patch_fetch():
            result = run(card_bonuses.search_cards())
        assert result["total"] == 3
        assert result["limit"] == 25
        assert result["offset"] == 0
        assert len(result["results"]) == 3

    def test_results_sorted_by_name(self):
        with _patch_fetch():
            result = run(card_bonuses.search_cards())
        names = [c["name"] for c in result["results"]]
        assert names == sorted(names, key=str.lower)

    def test_query_matches_name_and_issuer(self):
        with _patch_fetch():
            by_name = run(card_bonuses.search_cards(q="sapphire"))
            by_issuer = run(card_bonuses.search_cards(q="american_express"))
        assert by_name["total"] == 1
        assert by_name["results"][0]["cardId"] == "chase-sapphire"
        assert by_issuer["total"] == 1

    def test_filter_by_issuer_case_insensitive(self):
        with _patch_fetch():
            result = run(card_bonuses.search_cards(issuer="chase"))
        assert result["total"] == 2
        assert all(c["issuer"] == "CHASE" for c in result["results"])

    def test_filter_by_network(self):
        with _patch_fetch():
            result = run(card_bonuses.search_cards(network="VISA"))
        assert result["total"] == 1
        assert result["results"][0]["cardId"] == "chase-sapphire"

    def test_filter_by_is_business(self):
        with _patch_fetch():
            business = run(card_bonuses.search_cards(is_business=True))
            personal = run(card_bonuses.search_cards(is_business=False))
        assert business["total"] == 1
        assert business["results"][0]["cardId"] == "chase-ink"
        assert personal["total"] == 2

    def test_filter_by_max_annual_fee(self):
        with _patch_fetch():
            result = run(card_bonuses.search_cards(max_annual_fee=0))
        assert result["total"] == 1
        assert result["results"][0]["cardId"] == "amex-blue"

    def test_pagination(self):
        with _patch_fetch():
            page = run(card_bonuses.search_cards(limit=1, offset=1))
        assert page["total"] == 3
        assert page["limit"] == 1
        assert page["offset"] == 1
        assert len(page["results"]) == 1


class TestIssuersAndLookup:
    def test_get_issuers_deduped_and_sorted(self):
        with _patch_fetch():
            issuers = run(card_bonuses.get_issuers())
        assert issuers == ["AMERICAN_EXPRESS", "CHASE"]

    def test_get_card_by_id_found(self):
        with _patch_fetch():
            card = run(card_bonuses.get_card_by_id("chase-ink"))
        assert card is not None
        assert card["name"] == "Ink Business Preferred"

    def test_get_card_by_id_missing(self):
        with _patch_fetch():
            card = run(card_bonuses.get_card_by_id("nope"))
        assert card is None


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, payload=None, exc=None):
        self._payload = payload
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url):
        if self._exc is not None:
            raise self._exc
        return _FakeResponse(self._payload)


class TestFetchCaching:
    def test_fetches_and_caches(self):
        client = _FakeAsyncClient(payload=SAMPLE_CARDS)
        with patch.object(card_bonuses.httpx, "AsyncClient", return_value=client):
            first = run(card_bonuses._fetch_cards())
        assert len(first) == 3
        # Second call should hit the cache even with no client available.
        with patch.object(
            card_bonuses.httpx, "AsyncClient", side_effect=AssertionError("no refetch")
        ):
            second = run(card_bonuses._fetch_cards())
        assert second == first

    def test_force_bypasses_cache(self):
        with patch.object(
            card_bonuses.httpx, "AsyncClient", return_value=_FakeAsyncClient(payload=SAMPLE_CARDS)
        ):
            run(card_bonuses._fetch_cards())
        with patch.object(
            card_bonuses.httpx,
            "AsyncClient",
            return_value=_FakeAsyncClient(payload=SAMPLE_CARDS[:1]),
        ):
            refreshed = run(card_bonuses._fetch_cards(force=True))
        assert len(refreshed) == 1

    def test_serves_stale_on_failure(self):
        with patch.object(
            card_bonuses.httpx, "AsyncClient", return_value=_FakeAsyncClient(payload=SAMPLE_CARDS)
        ):
            run(card_bonuses._fetch_cards())
        # Expire the cache and force a failing refetch; stale copy should return.
        card_bonuses._cache["fetched_at"] = 0.0
        with patch.object(
            card_bonuses.httpx,
            "AsyncClient",
            return_value=_FakeAsyncClient(exc=httpx.ConnectError("boom")),
        ):
            result = run(card_bonuses._fetch_cards())
        assert len(result) == 3

    def test_cold_cache_failure_raises(self):
        with patch.object(
            card_bonuses.httpx,
            "AsyncClient",
            return_value=_FakeAsyncClient(exc=httpx.ConnectError("boom")),
        ):
            with pytest.raises(card_bonuses.CardBonusesError):
                run(card_bonuses._fetch_cards())

    def test_non_list_payload_raises(self):
        with patch.object(
            card_bonuses.httpx,
            "AsyncClient",
            return_value=_FakeAsyncClient(payload={"not": "a list"}),
        ):
            with pytest.raises(card_bonuses.CardBonusesError):
                run(card_bonuses._fetch_cards())


class TestCardBonusesAPI:
    def test_list_endpoint(self, client):
        with _patch_fetch():
            resp = client.get("/card-bonuses")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["results"]) == 3

    def test_list_endpoint_with_filters(self, client):
        with _patch_fetch():
            resp = client.get("/card-bonuses", params={"issuer": "CHASE", "limit": 5})
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_issuers_endpoint(self, client):
        with _patch_fetch():
            resp = client.get("/card-bonuses/issuers")
        assert resp.status_code == 200
        assert resp.json() == ["AMERICAN_EXPRESS", "CHASE"]

    def test_get_card_endpoint(self, client):
        with _patch_fetch():
            resp = client.get("/card-bonuses/chase-sapphire")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Chase Sapphire Preferred"

    def test_get_card_endpoint_404(self, client):
        with _patch_fetch():
            resp = client.get("/card-bonuses/missing")
        assert resp.status_code == 404
