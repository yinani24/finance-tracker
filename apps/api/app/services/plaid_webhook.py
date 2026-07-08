"""Plaid webhook request verification (Plaid-Verification JWT, ES256).

Plaid signs every webhook with a JWT in the ``Plaid-Verification`` header. The
JWT is signed (ES256) by a key we fetch from ``/webhook_verification_key/get``
using the ``kid`` in the JWT header, and it carries a ``request_body_sha256``
claim that binds the signature to the exact raw request body.

``verify_webhook`` performs, in order (cheap/structural checks before the
network + crypto):

1. Decode the JWT header only; require ``alg == "ES256"`` (never trust the
   token's own ``alg`` — defends ``alg=none`` / HS256-confusion).
2. Read the ``kid`` and fetch the matching verification key (cached by ``kid``
   so we don't hit Plaid per request; a rotated key is a new ``kid`` = a miss).
3. Verify the JWT signature against that key.
4. Enforce a 5-minute ``iat`` replay window (PyJWT does not do this for us).
5. Compare the ``request_body_sha256`` claim to ``sha256(raw_body)`` in
   constant time.

Verification is gated by ``settings.plaid_webhook_verify`` (env
``FT_PLAID_WEBHOOK_VERIFY``), which defaults to enabled; turning it off is the
escape hatch for exercising the endpoint locally without minting a real JWT.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from collections.abc import Mapping
from typing import Any

import jwt
from plaid.model.webhook_verification_key_get_request import (
    WebhookVerificationKeyGetRequest,
)

from app.config import settings
from app.services.plaid_service import get_plaid_client

logger = logging.getLogger(__name__)

# Maximum age (seconds) of a webhook's ``iat`` before we treat it as a replay.
_IAT_MAX_AGE_SECONDS = 300
# Small allowance for clock skew when a webhook's ``iat`` is slightly ahead.
_IAT_FUTURE_SKEW_SECONDS = 60

# Process-local cache of verification keys, keyed by JWT ``kid``. A rotated key
# arrives under a new ``kid`` (cache miss → fetch), so no explicit expiry is
# needed for correctness. Per-worker; fine for the single-owner MVP.
_KEY_CACHE: dict[str, dict[str, Any]] = {}


def _fetch_key(kid: str) -> dict[str, Any] | None:
    """Return the JWK dict for ``kid``, fetching + caching on miss."""
    cached = _KEY_CACHE.get(kid)
    if cached is not None:
        return cached

    client = get_plaid_client()
    request = WebhookVerificationKeyGetRequest(key_id=kid)
    response = client.webhook_verification_key_get(request)
    key_obj = response.key
    jwk = key_obj.to_dict() if hasattr(key_obj, "to_dict") else dict(key_obj)
    _KEY_CACHE[kid] = jwk
    return jwk


def verify_webhook(headers: Mapping[str, str], body: bytes) -> bool:
    """Return True if the webhook request is authentic.

    ``headers`` carries the ``Plaid-Verification`` JWT and ``body`` is the raw
    request bytes whose SHA-256 the JWT commits to. Returns True immediately
    when verification is disabled via ``FT_PLAID_WEBHOOK_VERIFY``.
    """
    if not settings.plaid_webhook_verify:
        return True

    token = headers.get("Plaid-Verification")
    if not token:
        return False

    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "ES256":
            return False
        kid = header.get("kid")
        if not kid:
            return False

        jwk = _fetch_key(kid)
        if jwk is None:
            return False

        # Build the public key from the JWK and verify the signature. Passing
        # algorithms=["ES256"] explicitly means the token's own alg is ignored.
        public_key = jwt.algorithms.ECAlgorithm.from_jwk(json.dumps(jwk))
        claims = jwt.decode(token, key=public_key, algorithms=["ES256"])
    except Exception:  # noqa: BLE001 — any decode/crypto failure is a rejection
        return False

    iat = claims.get("iat")
    if not isinstance(iat, (int, float)):
        return False
    age = time.time() - iat
    if age > _IAT_MAX_AGE_SECONDS or age < -_IAT_FUTURE_SKEW_SECONDS:
        return False

    claimed_hash = claims.get("request_body_sha256")
    if not isinstance(claimed_hash, str):
        return False
    actual_hash = hashlib.sha256(body).hexdigest()
    return hmac.compare_digest(claimed_hash, actual_hash)
