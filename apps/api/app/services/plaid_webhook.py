"""Plaid webhook request verification.

This is intentionally a **no-op pass-through** for now so the webhook endpoint
(issue #7) is testable and usable in sandbox/local without a public URL.

Issue #8 replaces the body of ``verify_webhook`` with real Plaid-Verification
JWT (ES256) validation against the key from ``/webhook_verification_key/get``,
including the body-hash claim check, gated by an ``FT_PLAID_WEBHOOK_VERIFY``
settings flag that defaults to enabled. The signature (headers + raw body) is
already what that real check needs, so #8 can slot in without touching the
route.
"""

from __future__ import annotations

from collections.abc import Mapping


def verify_webhook(headers: Mapping[str, str], body: bytes) -> bool:
    """Return True if the webhook request is authentic.

    Currently always returns True (verification is not yet wired up — see #8).
    ``headers`` carries the ``Plaid-Verification`` JWT and ``body`` is the raw
    request bytes whose hash the JWT commits to.
    """
    return True
