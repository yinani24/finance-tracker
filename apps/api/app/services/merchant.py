"""Merchant-name normalization — a base layer shared by every ingestion path.

Raw transaction descriptions arrive wrapped in payment-processor prefixes
(``SQ *``, ``TST*``, ``PP*`` …) and trailing location/phone noise. Left as-is,
the real merchant is hidden, so keyword categorization mislabels them (e.g.
``SQ *COFFEE BAR`` never matches ``coffee`` → lands in ``other``). Normalizing
here — before categorization and before we store ``normalized_merchant`` — lifts
the real name out so both classification and display improve.
"""

from __future__ import annotations

import re

# Pure payment-processor prefixes that wrap a *different* real merchant. Only
# these are stripped — NOT brand names like Amazon/Google/Apple/Uber, where the
# "prefix" IS the merchant and removing it would lose the name.
_PREFIX = re.compile(
    r"^\s*(?:"
    r"sq ?\*|tst ?\*|sp ?\*|pp ?\*|paypal ?\*|square ?\*|toast ?\*|clover ?\*|"
    r"clv ?\*|wpy ?\*|dd ?\*|gh ?\*|venmo ?\*|cash ?app ?\*"
    r")\s*",
    re.IGNORECASE,
)
# Trailing noise: a phone number, then a 2-letter state code, then a store #.
# The leading "<TOKEN>*" marker a processor stamps before the real merchant.
_PROCESSOR_TOKEN = re.compile(r"^\s*([A-Za-z]{2,8})\s*\*")
_TRAIL_PHONE = re.compile(r"\s+\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")
_TRAIL_STATE = re.compile(r"\s+[A-Za-z]{2}$")
_TRAIL_STORE = re.compile(r"\s+#?\d{3,}\b")
_WS = re.compile(r"\s+")


def extract_processor(raw: str) -> str | None:
    """Return the leading payment-processor token (``SQ``, ``TST``, ``DD`` …).

    Card networks record ``<PROCESSOR>*<REAL MERCHANT>``, so the processor is
    often a stronger category signal than the merchant name: a charge through
    Toast is a restaurant even when we've never heard of the restaurant.
    Returns the upper-cased token, or ``None`` when there is no ``*`` marker.
    """
    m = _PROCESSOR_TOKEN.match(raw or "")
    return m.group(1).upper() if m else None


def normalize_merchant(raw: str) -> str:
    """Return a cleaned merchant name: processor prefix + trailing phone/state/
    store-number noise removed and whitespace collapsed.

    Conservative — if stripping would empty the string, the original (trimmed)
    is kept so we never lose the merchant entirely.
    """
    original = (raw or "").strip()
    if not original:
        return ""
    s = _PREFIX.sub("", original)
    s = _TRAIL_PHONE.sub("", s)
    s = _TRAIL_STATE.sub("", s)
    s = _TRAIL_STORE.sub("", s)
    s = _WS.sub(" ", s).strip()
    return s or original
