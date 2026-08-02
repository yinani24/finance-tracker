from __future__ import annotations

import re

from app.services.enrichment.base import EnrichmentInput, EnrichmentResult
from app.services.enrichment.taxonomy import map_to_internal
from app.services.merchant import extract_processor, normalize_merchant

# Payment-processor token → category. The processor a charge is routed through
# is often a stronger signal than the merchant name: anything billed via Toast
# or SpotOn is a restaurant, even a local one we've never seen. Applied as a
# fallback AFTER the merchant keywords, so a known brand always wins.
_PROCESSOR_CATEGORIES: dict[str, str] = {
    # restaurant point-of-sale systems
    "TST": "dining",      # Toast
    "SPO": "dining",      # SpotOn
    "UEP": "dining",
    "PY": "dining",
    "SNACK": "dining",    # Snackpass
    "CHECKLE": "dining",  # Checkle
    # food delivery
    "DD": "dining",       # DoorDash
    "GH": "dining",       # Grubhub
    # grocery delivery
    "IC": "groceries",    # Instacart
    # ride / mobility
    "UBER": "transport",
    "LYFT": "transport",
    "BAYWHEE": "transport",  # Bay Wheels
    "SPIN": "transport",
    "LIME": "transport",
    # generic card-present processors — usually food/retail; dining is the
    # dominant real-world case for these in a consumer statement.
    "SQ": "dining",       # Square
    "CLV": "dining",      # Clover
}

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
            "starbucks", "dunkin*", "peet*", "coffee", "cafe", "restaurant", "grill",
            "bistro", "kitchen", "diner", "eatery", "tavern", "pizzeria", "pizza",
            "burger", "taco", "sushi", "ramen", "thai", "chipotle", "mcdonald*",
            "wendy*", "panera", "chick-fil", "shake shack", "olive garden", "subway",
            "deli", "bakery", "steakhouse", "brewery", "pub",
            # seen in real statements
            "dough", "noodle", "dumpling", "boba", "juice", "creamery",
            "ice cream", "donut", "bagel", "sandwich", "kebab", "curry",
            "bbq", "wings", "poke", "chaat", "jalebi", "mongolian", "farms",
            "szechuan", "sichuan", "hunan", "taqueria", "in-n-out", "in n out",
            "pho", "banh", "biryani", "tandoor", "dosa", "halal", "gyro",
            "chicken", "seafood", "buffet", "eats", "food", "snack", "bar &",
        ),
    ),
    # groceries
    (
        "groceries",
        (
            "whole foods", "trader joe*", "safeway", "kroger", "aldi", "costco",
            "wegmans", "publix", "sprouts", "food lion", "heb", "giant", "grocery",
            "supermarket", "market", "mart", "instacart",
        ),
    ),
    # travel (air + lodging)
    (
        "travel",
        (
            "airline", "airlines", "airways", "flight",
            # carriers as they actually appear on statements (often name+digits)
            "american air*", "united air*", "delta air*", "alaska air*",
            "spirit air*", "hawaiian air*", "sun country*", "southwest air*",
            "lugless", "clear me", "tsa",
            "delta", "united",
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
            "maverik", "casey*", "kum & go", "quiktrip", "circle k", "speedway",
            "sinclair", "sunoco", "valero", "gas station",
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
            # fees + billing services seen in real statements
            "interest charge", "annual membership fee", "late fee",
            "simple bills", "billing", "utilities",
        ),
    ),
    # entertainment / subscriptions
    (
        "entertainment",
        (
            "netflix", "spotify", "hulu", "disney+", "disney plus", "hbo", "max ",
            "youtube", "prime video", "apple music", "cinema", "movie", "theater",
            "amc ", "regal", "steam", "playstation", "xbox", "nintendo",
            "ticketmaster", "concert",
            # software / AI / SaaS subscriptions
            "anthropic", "claude.ai", "openai", "chatgpt", "github", "notion",
            "figma", "adobe", "dropbox", "icloud", "google one", "patreon",
            "substack", "medium", "audible", "kindle", "marcus theat", "marcus cor",
        ),
    ),
    # health / medical / fitness
    (
        "health",
        (
            "pharmacy", "cvs", "walgreens", "rite aid", "doctor", "medical",
            "dental", "dentist", "clinic", "hospital", "urgent care", "optometr",
            "gym", "fitness", "planet fit", "yoga", "pilates",
            # personal care
            "supercuts", "salon", "barber", "haircut", "spa", "nails",
        ),
    ),
    # shopping — broad, so kept late so category-specific stores win first
    (
        "shopping",
        (
            "amazon", "amzn", "target", "walmart", "best buy", "ebay", "etsy",
            "apple store",
            "nike", "adidas", "macy*", "nordstrom", "kohl*", "ikea", "home depot",
            "lowe*", "sephora", "ulta", "store", "shop",
            # seen in real statements
            "staples", "office depot", "books", "galleria", "mall",
            "outlet", "uniqlo", "zara", "h&m", "costco whse", "cvs pharmacy",
            "flower", "florist", "gift", "hardware", "supply",
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


def _compile(keywords: tuple[str, ...]) -> re.Pattern[str]:
    """Compile keywords into one alternation matched on WORD BOUNDARIES.

    Plain substring matching produced false positives — ``mobil`` (the gas
    brand) matched "Payment Thank You-**Mobil**e", filing card payments under
    transport. A boundary is only added where the keyword's edge is
    alphanumeric, so entries like ``booking.`` or ``pg&e`` still match.
    A trailing ``*`` marks a PREFIX keyword — no closing boundary — for merchants
    that run a code straight onto the name (``american air*`` matches
    ``AMERICAN AIR0017412354781``).
    """
    parts = []
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        prefix_only = kw.endswith("*")
        if prefix_only:
            kw = kw[:-1]
        lead = r"\b" if kw[0].isalnum() else ""
        trail = "" if prefix_only else (r"\b" if kw[-1].isalnum() else "")
        parts.append(f"{lead}{re.escape(kw)}{trail}")
    return re.compile("|".join(parts), re.IGNORECASE)


_COMPILED_RULES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (category, _compile(keywords)) for category, keywords in _RULES
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
        # which arrives with no category at all.
        if plaid_category:
            return map_to_internal(plaid_category), 0.6
        name = (merchant or "").lower()
        # 1. Known-merchant keywords (most specific).
        for category, pattern in _COMPILED_RULES:
            if pattern.search(name):
                return category, 0.9
        # 2. Payment-processor fallback: we don't recognise the merchant, but we
        #    know how the charge was routed (Toast/Square → a restaurant).
        processor = extract_processor(merchant)
        if processor:
            category = _PROCESSOR_CATEGORIES.get(processor)
            if category:
                return category, 0.7
        return "other", 0.3

    def enrich(self, txns: list[EnrichmentInput]) -> list[EnrichmentResult]:
        results: list[EnrichmentResult] = []
        for t in txns:
            # Classify on the RAW merchant (substring keyword matching already
            # sees through processor prefixes, and keeps brand tokens like
            # "amzn"). Store the normalized name for clean display + as the base
            # layer a future real classifier consumes.
            category, confidence = self._categorize(t.merchant, t.plaid_category)
            results.append(
                EnrichmentResult(
                    normalized_merchant=normalize_merchant(t.merchant).lower() or None,
                    category=category,
                    confidence=confidence,
                    raw_provider_category=t.plaid_category,
                )
            )
        return results
