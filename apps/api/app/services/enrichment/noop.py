from __future__ import annotations

from app.services.enrichment.base import EnrichmentInput, EnrichmentResult


class NoopProvider:
    """The default, keyless provider: enrichment as an identity function.

    It echoes back exactly what ``sync_transactions`` would have stored anyway —
    the raw Plaid category and a lowercased/stripped merchant — so wiring the
    enrichment hook in with this provider is behavior-preserving. No network
    calls, no secrets, hermetic in tests. Swapping in a real provider (slice 2)
    is a single ``FT_ENRICHMENT_PROVIDER`` change.
    """

    def enrich(self, txns: list[EnrichmentInput]) -> list[EnrichmentResult]:
        return [
            EnrichmentResult(
                normalized_merchant=(t.merchant or "").lower().strip() or None,
                category=t.plaid_category,
                confidence=None,
                raw_provider_category=t.plaid_category,
            )
            for t in txns
        ]
