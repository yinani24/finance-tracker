from __future__ import annotations

import logging

from app.config import settings
from app.services.enrichment.base import (
    EnrichmentInput,
    EnrichmentProvider,
    EnrichmentResult,
)
from app.services.enrichment.noop import NoopProvider
from app.services.enrichment.rules import RulesProvider

logger = logging.getLogger(__name__)

# Registry of available providers, keyed by the FT_ENRICHMENT_PROVIDER value.
# A richer provider ("ntropy"/"spade") can be added here later.
_PROVIDERS: dict[str, type] = {
    "noop": NoopProvider,
    "rules": RulesProvider,
}

__all__ = [
    "EnrichmentInput",
    "EnrichmentProvider",
    "EnrichmentResult",
    "NoopProvider",
    "RulesProvider",
    "get_provider",
]


def get_provider(name: str | None = None) -> EnrichmentProvider:
    """Return the configured enrichment provider (defaults to keyless ``noop``).

    An unknown/misconfigured provider name falls back to ``noop`` with a warning
    rather than raising, so a bad config value can never break transaction
    ingest — enrichment is an accuracy upgrade, not a correctness dependency.
    """
    key = (name or settings.enrichment_provider or "noop").lower()
    provider_cls = _PROVIDERS.get(key)
    if provider_cls is None:
        logger.warning(
            "unknown enrichment provider %r; falling back to noop", key
        )
        provider_cls = NoopProvider
    return provider_cls()
