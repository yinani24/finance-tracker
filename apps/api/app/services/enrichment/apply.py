from __future__ import annotations

import logging
from datetime import datetime, timezone
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
    enriched_at = datetime.now(timezone.utc)
    for (row, _), result in zip(rows, results):
        if result.category is not None:
            row.category = result.category
            # Record provenance only when the provider actually classified the
            # row: `category_confidence` powers the low-confidence recategorize
            # UI, and `enriched_at` marks the row as processed so a later
            # backfill can target `enriched_at IS NULL`. Fail-open / noop rows
            # (category None) stay unstamped and remain backfill candidates.
            row.category_confidence = result.confidence
            row.enriched_at = enriched_at
        if result.normalized_merchant is not None:
            row.normalized_merchant = result.normalized_merchant
