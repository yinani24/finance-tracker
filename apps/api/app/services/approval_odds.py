"""Estimated approval odds for a credit-card recommendation.

Ranking purely by first-year value recommends cards the user may not be able to
get: an $895 premium card is worthless advice at a 640 score, and a Chase card
is near-hopeless once someone is over 5/24. This module estimates the
*likelihood of approval* so the recommender can rank by **expected** value
(value x odds) rather than headline value.

This is a transparent heuristic over public, well-documented issuer behaviour —
score bands and Chase's 5/24 rule — not a credit model. It never claims
precision: odds are coarse bands, every estimate carries a plain-language
reason, and with no profile supplied every card scores 1.0 so ranking behaviour
is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Coarse FICO bands. Kept as an ordered scale so tiers can be compared.
SCORE_BANDS: tuple[str, ...] = ("poor", "fair", "good", "excellent")
_BAND_INDEX = {b: i for i, b in enumerate(SCORE_BANDS)}

# Approximate FICO floors, used to map a raw score onto a band.
_BAND_FLOORS = ((740, "excellent"), (670, "good"), (580, "fair"), (0, "poor"))

# Card tiers, inferred from the annual fee. Premium cards demand stronger
# profiles; no-fee entry cards are the most attainable.
_PREMIUM_FEE = 395.0
_MID_FEE = 95.0

# odds[tier][band] — deliberately coarse; these are bands, not predictions.
_ODDS: dict[str, dict[str, float]] = {
    "premium": {"excellent": 0.85, "good": 0.45, "fair": 0.12, "poor": 0.03},
    "mid": {"excellent": 0.92, "good": 0.70, "fair": 0.30, "poor": 0.08},
    "entry": {"excellent": 0.95, "good": 0.85, "fair": 0.60, "poor": 0.25},
}

# Issuers that decline almost regardless of score once the applicant has opened
# too many cards recently (Chase's "5/24"). Publicly documented, widely relied on.
_VELOCITY_RULES: dict[str, int] = {"CHASE": 5}
_VELOCITY_ODDS = 0.05


@dataclass(frozen=True)
class ApprovalProfile:
    """What we know about the applicant's credit standing.

    Every field is optional: with nothing supplied, odds estimation is skipped
    entirely rather than guessed at.
    """

    score_band: Optional[str] = None
    # Cards opened in the last 24 months — drives issuer velocity rules.
    recent_applications: Optional[int] = None

    @classmethod
    def from_score(cls, score: int | None, **kwargs) -> "ApprovalProfile":
        return cls(score_band=band_for_score(score), **kwargs)

    @property
    def is_known(self) -> bool:
        return self.score_band in _BAND_INDEX


def band_for_score(score: int | None) -> Optional[str]:
    """Map a raw FICO score onto a coarse band (``None`` if unknown)."""
    if score is None:
        return None
    for floor, band in _BAND_FLOORS:
        if score >= floor:
            return band
    return "poor"


def card_tier(card: dict) -> str:
    """Classify a card as ``premium`` / ``mid`` / ``entry`` by annual fee."""
    fee = float(card.get("annualFee") or 0)
    if fee >= _PREMIUM_FEE:
        return "premium"
    if fee >= _MID_FEE:
        return "mid"
    return "entry"


def estimate_approval_odds(
    card: dict, profile: ApprovalProfile | None
) -> tuple[float, Optional[str]]:
    """Return ``(odds, reason)`` for one card.

    ``odds`` is 0..1. With no usable profile it is ``1.0`` and ``reason`` is
    ``None``, so callers that lack a credit profile rank exactly as before.
    """
    if profile is None or not profile.is_known:
        return 1.0, None

    band = profile.score_band or "good"
    tier = card_tier(card)

    # Issuer velocity rules dominate everything else when tripped.
    issuer = (card.get("issuer") or "").upper()
    limit = _VELOCITY_RULES.get(issuer)
    if limit is not None and (profile.recent_applications or 0) >= limit:
        return (
            _VELOCITY_ODDS,
            f"{issuer.title()} rarely approves applicants with "
            f"{profile.recent_applications} cards opened in the last 24 months.",
        )

    odds = _ODDS[tier][band]

    # Business cards ask for a business profile on top of personal credit, so
    # they are meaningfully harder for a personal applicant.
    if card.get("isBusiness"):
        odds *= 0.7

    reason = (
        f"{tier.title()} card with a {band} credit profile"
        + (" (business card)" if card.get("isBusiness") else "")
        + "."
    )
    return round(min(odds, 1.0), 2), reason


def odds_label(odds: float) -> str:
    """A plain-language band for display — never a false-precision percentage."""
    if odds >= 0.8:
        return "excellent"
    if odds >= 0.55:
        return "good"
    if odds >= 0.25:
        return "fair"
    return "poor"
