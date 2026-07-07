"""Domain-level translation of Plaid SDK errors into safe HTTP responses.

This module is intentionally framework-agnostic (no FastAPI import) so the
service layer can raise a ``PlaidError`` without depending on the web layer.
``app.main`` registers a single exception handler that renders these into
sanitized JSON responses.

Security: only the whitelisted ``error_code`` (and a derived ``action``) is
ever surfaced. The raw Plaid response body — which can contain
``error_message``, ``request_id``, and request context — and the item's
``access_token`` are never propagated into responses or logs.
"""

from __future__ import annotations

import json

import plaid

# Item is broken and the user must re-authenticate (re-link) to recover.
_RELINK_CODES = {
    "ITEM_LOGIN_REQUIRED",
    "INVALID_ACCESS_TOKEN",
    "INVALID_CREDENTIALS",
    "ITEM_NOT_FOUND",
    "ACCESS_NOT_GRANTED",
}

# Transient conditions — the caller can safely retry later.
_RETRY_CODES = {
    "RATE_LIMIT_EXCEEDED",
    "INTERNAL_SERVER_ERROR",
    "PLANNED_MAINTENANCE",
}


class PlaidError(Exception):
    """A classified Plaid failure carrying only safe-to-surface fields."""

    def __init__(self, http_status: int, error_code: str, action: str | None = None):
        self.http_status = http_status
        self.error_code = error_code
        self.action = action
        super().__init__(error_code)


def _extract_error_code(exc: plaid.ApiException) -> str:
    """Pull ``error_code`` out of the Plaid response body defensively.

    The SDK does not guarantee a JSON body on every error path, so any
    parse failure falls back to ``"UNKNOWN"``.
    """
    body = getattr(exc, "body", None)
    if not body:
        return "UNKNOWN"
    try:
        parsed = json.loads(body)
    except (ValueError, TypeError):
        return "UNKNOWN"
    if isinstance(parsed, dict):
        return parsed.get("error_code") or "UNKNOWN"
    return "UNKNOWN"


def map_plaid_exception(exc: plaid.ApiException) -> PlaidError:
    """Classify a ``plaid.ApiException`` into a :class:`PlaidError`.

    - Re-link codes -> 409 with ``action="relink"``.
    - Transient codes, HTTP 429, or Plaid 5xx -> 503 with ``action="retry"``.
    - Everything else -> 502 (bad upstream), carrying only the ``error_code``.
    """
    code = _extract_error_code(exc)
    status = getattr(exc, "status", None)

    if code in _RELINK_CODES:
        return PlaidError(409, code, action="relink")
    if (
        code in _RETRY_CODES
        or status == 429
        or (isinstance(status, int) and status >= 500)
    ):
        return PlaidError(503, code, action="retry")
    return PlaidError(502, code)
