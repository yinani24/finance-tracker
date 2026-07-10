from __future__ import annotations

from typing import Optional

# The fixed internal category set. Providers (and Plaid) return their own labels;
# everything is mapped into this set at the boundary so downstream consumers (the
# spending profile in `spending_profile.py`, and the recommendation engine) stay
# vendor-agnostic. `dining` is the Phase-2 priority (see docs/prd/PRODUCT.md).
INTERNAL_CATEGORIES: tuple[str, ...] = (
    "dining",
    "groceries",
    "travel",
    "transport",
    "shopping",
    "bills",
    "entertainment",
    "health",
    "income",
    "other",
)

# Known upstream labels → internal category. Keys are normalized (lowercased,
# `_`/`&` collapsed to spaces — see `_normalize`). This covers Plaid's
# `personal_finance_category.primary` set plus common enrichment-vendor synonyms
# so a provider swap (Plaid → Ntropy/Spade) needs no change here. Anything not
# listed maps to `other` — the safe fallback.
_ALIASES: dict[str, str] = {
    # dining
    "food and drink": "dining",
    "dining": "dining",
    "restaurants": "dining",
    "fast food": "dining",
    "coffee": "dining",
    # Plaid `personal_finance_category.detailed` food splits. Plaid's *primary*
    # FOOD_AND_DRINK conflates groceries with restaurants; the detailed label
    # separates them (see plaid_service). Groceries → groceries; everything else
    # edible → dining.
    "food and drink groceries": "groceries",
    "food and drink restaurant": "dining",
    "food and drink coffee": "dining",
    "food and drink fast food": "dining",
    "food and drink beer wine and liquor": "dining",
    "food and drink vending machines": "dining",
    "food and drink other": "dining",
    # groceries (a real provider can distinguish these from dining; Plaid's
    # primary category cannot, which is exactly why the detailed split above and
    # enrichment exist)
    "groceries": "groceries",
    "grocery": "groceries",
    "supermarkets": "groceries",
    # travel
    "travel": "travel",
    "airlines": "travel",
    "hotels": "travel",
    "lodging": "travel",
    # transport
    "transportation": "transport",
    "transport": "transport",
    "transit": "transport",
    "gas": "transport",
    "fuel": "transport",
    "rideshare": "transport",
    "ride share": "transport",
    "parking": "transport",
    # shopping
    "general merchandise": "shopping",
    "shopping": "shopping",
    "retail": "shopping",
    "home improvement": "shopping",
    # bills
    "rent and utilities": "bills",
    "utilities": "bills",
    "bills": "bills",
    "loan payments": "bills",
    "bank fees": "bills",
    "government and non profit": "bills",
    "subscriptions": "bills",
    # entertainment
    "entertainment": "entertainment",
    "streaming": "entertainment",
    # health
    "medical": "health",
    "health": "health",
    "healthcare": "health",
    "personal care": "health",
    "pharmacy": "health",
    "fitness": "health",
    # income
    "income": "income",
    "salary": "income",
    "payroll": "income",
    # explicitly-not-income money movement → other
    "transfer in": "other",
    "transfer out": "other",
    "general services": "other",
}


def _normalize(raw: str) -> str:
    # Lowercase, turn `_`/`&` into word separators, and collapse whitespace so
    # "FOOD_AND_DRINK", "food and drink", and "Food & Drink" all map alike.
    cleaned = raw.strip().lower().replace("_", " ").replace("&", " and ")
    return " ".join(cleaned.split())


def map_to_internal(raw: Optional[str]) -> str:
    """Map an upstream category label into our fixed internal set.

    Returns ``"other"`` for unknown, empty, or ``None`` inputs so a mystery label
    never silently propagates as a real category.
    """
    if not raw:
        return "other"
    return _ALIASES.get(_normalize(raw), "other")
