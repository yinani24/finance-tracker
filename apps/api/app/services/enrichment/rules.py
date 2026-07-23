from __future__ import annotations

from app.services.enrichment.base import EnrichmentInput, EnrichmentResult
from app.services.enrichment.taxonomy import map_to_internal

# Ordered merchant-keyword rules → internal taxonomy category. First rule with a
# keyword that appears (as a substring) in the normalized merchant name wins, so
# more specific rules must come before broader ones (e.g. delivery dining before
# a bare "uber" → transport). Keyless and offline — no network, no secrets.
_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # dining — includes food-delivery, which must beat "uber" (transport) below
    (
        "dining",
        (
            "doordash", "uber eats", "ubereats", "grubhub", "postmates", "seamless",
            "starbucks", "dunkin", "peet", "coffee", "cafe", "restaurant", "grill",
            "bistro", "kitchen", "diner", "eatery", "tavern", "pizzeria", "pizza",
            "burger", "taco", "sushi", "ramen", "thai", "chipotle", "mcdonald",
            "wendy", "panera", "chick-fil", "shake shack", "olive garden", "subway",
            "deli", "bakery", "steakhouse", "brewery", "pub ",
        ),
    ),
    # groceries
    (
        "groceries",
        (
            "whole foods", "trader joe", "safeway", "kroger", "aldi", "costco",
            "wegmans", "publix", "sprouts", "food lion", "heb", "giant", "grocery",
            "supermarket", "market", "mart", "instacart",
        ),
    ),
    # travel (air + lodging)
    (
        "travel",
        (
            "airline", "airlines", "airways", " air ", "flight", "delta", "united",
            "southwest", "jetblue", "alaska air", "spirit air", "frontier",
            "hotel", "marriott", "hilton", "hyatt", "airbnb", "expedia", "booking.",
            "priceline", "resort", "motel", "inn ", "lodge",
        ),
    ),
    # transport (ground)
    (
        "transport",
        (
            "uber", "lyft", "shell", "chevron", "exxon", "mobil", "arco", "76 ",
            "bp ", "gas ", "fuel", "parking", "toll", "transit", "metro", "bart",
            "amtrak", "caltrain", "dmv", "rental car", "hertz", "enterprise rent",
        ),
    ),
    # bills / utilities / recurring
    (
        "bills",
        (
            "rent", "mortgage", "electric", "pg&e", "utility", "water district",
            "verizon", "at&t", "t-mobile", "sprint", "comcast", "xfinity",
            "spectrum", "internet", "wireless", "insurance", "geico", "state farm",
            "student loan", "loan pmt",
        ),
    ),
    # entertainment / subscriptions
    (
        "entertainment",
        (
            "netflix", "spotify", "hulu", "disney+", "disney plus", "hbo", "max ",
            "youtube", "prime video", "apple music", "cinema", "movie", "theater",
            "amc ", "regal", "steam", "playstation", "xbox", "nintendo",
            "ticketmaster", "concert", "spa ",
        ),
    ),
    # health / medical / fitness
    (
        "health",
        (
            "pharmacy", "cvs", "walgreens", "rite aid", "doctor", "medical",
            "dental", "dentist", "clinic", "hospital", "urgent care", "optometr",
            "gym", "fitness", "planet fit", "yoga", "pilates",
        ),
    ),
    # shopping — broad, so kept late so category-specific stores win first
    (
        "shopping",
        (
            "amazon", "target", "walmart", "best buy", "ebay", "etsy", "apple store",
            "nike", "adidas", "macy", "nordstrom", "kohl", "ikea", "home depot",
            "lowe", "sephora", "ulta", "store", "shop",
        ),
    ),
    # income
    (
        "income",
        (
            "payroll", "salary", "direct dep", "direct deposit", "paycheck",
            "ach credit", "interest paid", "dividend", "refund", "reimburse",
        ),
    ),
)


class RulesProvider:
    """Keyless, offline categorizer: assigns an internal-taxonomy category from
    merchant-name keyword rules.

    Falls back to the upstream (Plaid) category mapped into our taxonomy when no
    rule matches, and to ``"other"`` when there is nothing to go on — so a
    transaction is never left uncategorized. This is what turns statement-import
    data (which arrives with no category) into a real spending breakdown that the
    recommendation engine can rank by. Swap in a richer provider later via
    ``FT_ENRICHMENT_PROVIDER`` without touching callers.
    """

    def _categorize(self, merchant: str, plaid_category: str | None) -> tuple[str, float]:
        # Trust an upstream (Plaid) category when we have one — it's already
        # classified. Merchant rules are the signal for statement-import data,
        # which arrives with no category at all. Fall back to "other".
        if plaid_category:
            return map_to_internal(plaid_category), 0.6
        name = (merchant or "").lower()
        for category, keywords in _RULES:
            if any(kw in name for kw in keywords):
                return category, 0.9
        return "other", 0.3

    def enrich(self, txns: list[EnrichmentInput]) -> list[EnrichmentResult]:
        results: list[EnrichmentResult] = []
        for t in txns:
            category, confidence = self._categorize(t.merchant, t.plaid_category)
            results.append(
                EnrichmentResult(
                    normalized_merchant=(t.merchant or "").lower().strip() or None,
                    category=category,
                    confidence=confidence,
                    raw_provider_category=t.plaid_category,
                )
            )
        return results
