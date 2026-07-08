from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel


class EnrichmentInput(BaseModel):
    """A single stored transaction handed to an enrichment provider.

    ``plaid_category`` is the raw upstream category we already have (Plaid's
    ``personal_finance_category.primary``, lowercased). It is passed through so
    providers can use it as a hint and so the keyless ``noop`` provider can echo
    it back unchanged.
    """

    external_id: Optional[str] = None
    merchant: str
    amount: float
    plaid_category: Optional[str] = None


class EnrichmentResult(BaseModel):
    """A provider's enrichment for one transaction.

    ``category`` is expected to already be mapped into OUR internal taxonomy (see
    ``taxonomy.map_to_internal``), not the vendor's raw label — that keeps every
    downstream consumer (spending profile, recommendation engine) vendor-agnostic.
    ``raw_provider_category`` preserves the vendor's original label for debugging.
    """

    normalized_merchant: Optional[str] = None
    category: Optional[str] = None
    confidence: Optional[float] = None
    raw_provider_category: Optional[str] = None


@runtime_checkable
class EnrichmentProvider(Protocol):
    """Provider-swappable enrichment over stored transactions.

    Implementations MUST be safe to call with an empty list and MUST return
    exactly one ``EnrichmentResult`` per input, in the same order. The interface
    is synchronous because the sole caller (``sync_transactions``) runs in a
    synchronous request path; a provider that talks to a network API should make
    its calls synchronously (e.g. an httpx sync client) rather than forcing an
    event loop onto the caller.
    """

    def enrich(self, txns: list[EnrichmentInput]) -> list[EnrichmentResult]: ...
