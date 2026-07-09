from __future__ import annotations

import logging
from typing import Any

from app.services.enrichment import get_provider
from app.services.enrichment.base import EnrichmentInput

logger = logging.getLogger(__name__)


def apply_enrichment(rows: list[tuple[Any, EnrichmentInput]]) -> None:
    """Enrich a batch of freshly-built transaction rows in place.

    ``rows`` pairs each ORM ``Transaction`` (anything exposing ``category`` /
    ``normalized_merchant``) with the ``EnrichmentInput`` describing it. Shared
    by the Plaid-sync and statement-import ingest paths so both categorize
    identically.

    Fail-open by design: if the provider errors or returns a mismatched batch,
    log and leave the raw values untouched. Enrichment is an accuracy upgrade,
    not a correctness dependency — a provider outage must never break ingest.
    With the default ``noop`` provider this is a no-op.
    """
    if not rows:
        return
    provider = get_provider()
    inputs = [inp for _, inp in rows]
    try:
        results = provider.enrich(inputs)
    except Exception:  # noqa: BLE001 - provider is untrusted; never break ingest
        logger.warning(
            "enrichment provider failed; keeping raw categories",
            exc_info=True,
        )
        return
    if len(results) != len(inputs):
        logger.warning(
            "enrichment returned %d results for %d inputs; keeping raw categories",
            len(results),
            len(inputs),
        )
        return
    for (row, _), result in zip(rows, results):
        if result.category is not None:
            row.category = result.category
        if result.normalized_merchant is not None:
            row.normalized_merchant = result.normalized_merchant
