"""Client for the credit-card sign-up-bonus dataset.

finance-tracker consumes the sibling ``credit-card-bonuses-api`` project
(https://github.com/yinani24/credit-card-bonuses-api), which publishes a static
JSON export of credit-card sign-up bonuses, rates, and metadata. This module is
the single fetch/cache/query layer over that export; the ``/card-bonuses`` API
router and the recommendation snapshot service both depend on it.

The upstream export is a JSON list of card objects with camelCase keys::

    {
        "cardId": "90436ebe...",
        "name": "Delta SkyMiles Blue",
        "issuer": "AMERICAN_EXPRESS",
        "network": "AMERICAN_EXPRESS",
        "isBusiness": false,
        "annualFee": 0,
        "universalCashbackPercent": 1,
        "url": "https://...",
        "offers": [...],
        ...
    }
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

# Raw JSON export from the sibling repo's default (``master``) branch.
DATA_URL = (
    "https://raw.githubusercontent.com/yinani24/"
    "credit-card-bonuses-api/master/exports/data.json"
)
CACHE_TTL_SECONDS = 3600
_REQUEST_TIMEOUT_SECONDS = 15.0

# Process-wide cache shared across requests. ``data`` is the parsed list or None.
_cache: Dict[str, Any] = {"data": None, "fetched_at": 0.0}


class CardBonusesError(RuntimeError):
    """Raised when the upstream dataset cannot be fetched or parsed."""


def _data_url() -> str:
    """Resolve the export URL, allowing an override via ``FT_CARD_BONUSES_URL``."""
    return getattr(settings, "card_bonuses_url", "") or DATA_URL


def clear_cache() -> None:
    """Reset the in-memory cache (used by tests)."""
    _cache["data"] = None
    _cache["fetched_at"] = 0.0


async def _fetch_cards(force: bool = False) -> List[Dict[str, Any]]:
    """Fetch and cache the card dataset.

    Returns the cached copy while it is fresh (within ``CACHE_TTL_SECONDS``). On
    an upstream failure a stale cached copy is served if available; only a cold
    cache surfaces the error as :class:`CardBonusesError`.
    """
    now = time.time()
    cached = _cache["data"]
    if not force and cached is not None and now - _cache["fetched_at"] < CACHE_TTL_SECONDS:
        return cached

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            resp = await client.get(_data_url())
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        if cached is not None:
            # Serve stale data rather than failing a user-facing request.
            return cached
        raise CardBonusesError(f"Failed to fetch card bonuses: {exc}") from exc

    if not isinstance(data, list):
        if cached is not None:
            return cached
        raise CardBonusesError("Unexpected card bonuses payload (expected a JSON list)")

    _cache["data"] = data
    _cache["fetched_at"] = now
    return data


def fetch_cards_sync(force: bool = False) -> List[Dict[str, Any]]:
    """Synchronous fetch/cache of the card dataset — the single source of truth.

    Shares the same process-wide ``_cache`` as the async :func:`_fetch_cards`, so
    synchronous callers (the insight engine, recommendation snapshots) and async
    callers (the ``/card-bonuses`` router) all read one dataset from one upstream
    (the sibling ``credit-card-bonuses-api``). Serves a stale cached copy on an
    upstream failure; only a cold cache surfaces the error as
    :class:`CardBonusesError`.
    """
    now = time.time()
    cached = _cache["data"]
    if not force and cached is not None and now - _cache["fetched_at"] < CACHE_TTL_SECONDS:
        return cached

    try:
        resp = httpx.get(_data_url(), timeout=_REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        if cached is not None:
            return cached
        raise CardBonusesError(f"Failed to fetch card bonuses: {exc}") from exc

    if not isinstance(data, list):
        if cached is not None:
            return cached
        raise CardBonusesError("Unexpected card bonuses payload (expected a JSON list)")

    _cache["data"] = data
    _cache["fetched_at"] = now
    return data


def _matches(
    card: Dict[str, Any],
    *,
    q: Optional[str],
    issuer: Optional[str],
    network: Optional[str],
    is_business: Optional[bool],
    max_annual_fee: Optional[float],
) -> bool:
    if q:
        needle = q.lower()
        haystack = f"{card.get('name', '')} {card.get('issuer', '')}".lower()
        if needle not in haystack:
            return False
    if issuer and (card.get("issuer") or "").upper() != issuer.upper():
        return False
    if network and (card.get("network") or "").upper() != network.upper():
        return False
    if is_business is not None and bool(card.get("isBusiness", False)) != is_business:
        return False
    if max_annual_fee is not None and (card.get("annualFee") or 0) > max_annual_fee:
        return False
    return True


async def search_cards(
    *,
    q: Optional[str] = None,
    issuer: Optional[str] = None,
    network: Optional[str] = None,
    is_business: Optional[bool] = None,
    max_annual_fee: Optional[float] = None,
    limit: int = 25,
    offset: int = 0,
) -> Dict[str, Any]:
    """Return a paginated, filtered slice of the card dataset."""
    cards = await _fetch_cards()
    matched = [
        card
        for card in cards
        if _matches(
            card,
            q=q,
            issuer=issuer,
            network=network,
            is_business=is_business,
            max_annual_fee=max_annual_fee,
        )
    ]
    # Stable ordering by name so pagination is deterministic across requests.
    matched.sort(key=lambda c: (c.get("name") or "").lower())
    window = matched[offset : offset + limit]
    return {
        "total": len(matched),
        "limit": limit,
        "offset": offset,
        "results": window,
    }


async def get_issuers() -> List[str]:
    """Return the sorted set of distinct issuers in the dataset."""
    cards = await _fetch_cards()
    issuers = {(card.get("issuer") or "").strip() for card in cards}
    issuers.discard("")
    return sorted(issuers)


async def get_card_by_id(card_id: str) -> Optional[Dict[str, Any]]:
    """Return a single card by its ``cardId``, or None if not found."""
    cards = await _fetch_cards()
    for card in cards:
        if card.get("cardId") == card_id:
            return card
    return None
