from __future__ import annotations

from app.services.enrichment.base import EnrichmentInput, EnrichmentResult
from app.services.enrichment.taxonomy import map_to_internal


class NoopProvider:
    """The default, keyless provider: maps the raw upstream category into our
    internal taxonomy and normalizes the merchant — no network calls, no secrets.

    Per the provider contract (``base.py``), ``category`` must already be in OUR
    internal taxonomy, not the vendor's raw label. So this maps ``plaid_category``
    through :func:`taxonomy.map_to_internal` rather than echoing it — that is what
    keeps downstream consumers (spending profile, recommendation engine) vendor-
    agnostic. ``raw_provider_category`` preserves the original label for debugging.

    A ``None`` upstream category is passed through as ``None`` (not mapped to
    ``"other"``) so ``apply_enrichment`` leaves the row's category untouched — the
    statement-import path (which has no Plaid category and derives its own) relies
    on this no-overwrite behavior. Swapping in a real provider is a single
    ``FT_ENRICHMENT_PROVIDER`` change.
    """

    def enrich(self, txns: list[EnrichmentInput]) -> list[EnrichmentResult]:
        return [
            EnrichmentResult(
                normalized_merchant=(t.merchant or "").lower().strip() or None,
                category=(
                    map_to_internal(t.plaid_category) if t.plaid_category else None
                ),
                confidence=None,
                raw_provider_category=t.plaid_category,
            )
            for t in txns
        ]
