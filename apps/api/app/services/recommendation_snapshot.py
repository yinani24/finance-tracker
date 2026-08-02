from __future__ import annotations

import hashlib
import json
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.card import Card
from app.repositories.recommendation_snapshot import RecommendationSnapshotRepository
from app.services.card_bonuses import fetch_cards_sync
from app.services.card_recommendation import CardRecommendationService
from app.services.spending_profile import get_or_refresh as get_or_refresh_profile


def _fetch_cards() -> List[Dict]:
    """Return the card dataset from the single ``card_bonuses`` source.

    Delegates to :func:`app.services.card_bonuses.fetch_cards_sync` (one upstream,
    one shared cache). Kept as a module-level name so tests can patch this seam.
    """
    return fetch_cards_sync()


def _compute_inputs_hash(*parts: object) -> str:
    """Fingerprint every input that affects the recommendation output.

    The cached snapshot is only valid while *all* of its inputs are unchanged:
    the user's spending profile, the cards they own, the card **dataset** the
    recommendations are ranked over, and the point valuation. Leaving any of
    these out lets a stale snapshot survive a real input change — e.g. an
    upstream sign-up-bonus refresh (PRD FR5, freshness).
    """
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class RecommendationSnapshotService:
    def __init__(self, db: Session):
        self.db = db
        self.snapshot_repo = RecommendationSnapshotRepository(db)
        self.rec_service = CardRecommendationService()

    def _get_user_cards(self, user_id: int) -> List[Dict]:
        stmt = select(Card).where(Card.user_id == user_id)
        cards = list(self.db.scalars(stmt).all())
        return [
            {
                "name": c.name,
                "issuer": c.issuer or "",
                "network": c.network,
                "annual_fee": c.annual_fee,
            }
            for c in cards
        ]

    def _profile_to_read(self, profile) -> Dict:
        return {
            "user_id": profile.user_id,
            "period_start": str(profile.period_start),
            "period_end": str(profile.period_end),
            "avg_monthly_spend": profile.avg_monthly_spend,
            "categories": [
                {"category": k, "monthly_avg": v}
                for k, v in json.loads(profile.category_breakdown_json).items()
            ],
            "top_merchants": json.loads(profile.top_merchants_json),
            "computed_at": str(profile.computed_at),
        }

    def _get_approval_profile(self, user_id: int):
        """Build an ``ApprovalProfile`` from the user's stored credit standing.

        Returns ``None`` when no band has been set, which makes odds estimation
        a no-op and leaves the ranking on headline value.
        """
        from app.models.user import UserPreference
        from app.services.approval_odds import ApprovalProfile

        pref = self.db.get(UserPreference, user_id)
        if not pref or not pref.credit_score_band:
            return None
        return ApprovalProfile(
            score_band=pref.credit_score_band,
            recent_applications=pref.recent_card_applications,
        )

    def get_recommendations(self, user_id: int, rec_type: str) -> Dict:
        profile = get_or_refresh_profile(self.db, user_id)
        user_cards = self._get_user_cards(user_id)

        # Fetch the card dataset up front so its contents are part of the cache
        # key. The dataset — not just the user's profile and owned cards —
        # determines the ranking, so when upstream sign-up bonuses or cards
        # change the cached snapshot must be recomputed (PRD FR5, freshness).
        # ``fetch_cards_sync`` is a process-wide TTL cache, so this is an
        # in-memory read on the hot path, not an extra upstream round-trip.
        available_cards = _fetch_cards()

        # The user's credit standing changes the RANKING (expected value =
        # value x approval odds), so it belongs in the cache key too.
        approval_profile = self._get_approval_profile(user_id)

        profile_json = profile.category_breakdown_json + str(profile.avg_monthly_spend)
        user_cards_json = json.dumps(user_cards, sort_keys=True)
        dataset_json = json.dumps(available_cards, sort_keys=True)
        current_hash = _compute_inputs_hash(
            profile_json,
            user_cards_json,
            dataset_json,
            settings.points_value_cents,
            f"{approval_profile.score_band}:{approval_profile.recent_applications}"
            if approval_profile
            else "no-credit-profile",
        )

        # Check cache
        existing = self.snapshot_repo.get(user_id, rec_type)
        if existing and existing.inputs_hash == current_hash:
            cached = json.loads(existing.results_json)
            return {
                **self._shape_payload(rec_type, cached),
                "spending_profile": self._profile_to_read(profile),
            }

        # Recompute (dataset already fetched above)
        profile_dict = {
            "avg_monthly_spend": profile.avg_monthly_spend,
            "category_breakdown": json.loads(profile.category_breakdown_json),
            "top_merchants": json.loads(profile.top_merchants_json),
        }

        if rec_type == "next_card":
            # Cached as a bare list of recommendations (unchanged shape).
            to_cache: object = self.rec_service.recommend_next_card(
                profile_dict,
                user_cards,
                available_cards,
                points_value_cents=settings.points_value_cents,
                approval_profile=approval_profile,
            )
        else:
            # Portfolio: cache the per-card analyses AND the per-category "best
            # held card" assignments as one blob, so both survive a cache hit
            # (which returns the stored blob verbatim without recomputing). The
            # two are computed from the same profile/cards, so they stay
            # consistent. See _shape_payload for how this is unwrapped on read.
            to_cache = {
                "cards": self.rec_service.analyze_portfolio(
                    profile_dict, user_cards, available_cards
                ),
                "category_assignments": self.rec_service.best_card_per_category(
                    profile_dict, user_cards, available_cards
                ),
            }

        self.snapshot_repo.upsert(
            user_id=user_id,
            rec_type=rec_type,
            results_json=json.dumps(to_cache),
            inputs_hash=current_hash,
        )

        return {
            **self._shape_payload(rec_type, to_cache),
            "spending_profile": self._profile_to_read(profile),
        }

    @staticmethod
    def _shape_payload(rec_type: str, cached: object) -> Dict:
        """Shape a cached blob into the response body (minus ``spending_profile``).

        Used identically on the cache-hit and cold paths so the two can't drift
        (the double-nesting class of bug). ``next_card`` snapshots store a bare
        list under ``recommendations``; ``portfolio_gap`` snapshots store the
        combined ``{"cards", "category_assignments"}`` dict and are returned
        spread. A legacy portfolio snapshot cached as a bare list (before
        ``category_assignments`` existed) is wrapped defensively so a pre-existing
        cache entry never crashes on read; it refreshes on the next input change.
        """
        if rec_type == "next_card":
            return {"recommendations": cached}
        if isinstance(cached, list):
            return {"cards": cached, "category_assignments": []}
        return dict(cached)  # type: ignore[arg-type]

    def invalidate(self, user_id: int) -> None:
        for rec_type in ("next_card", "portfolio_gap"):
            existing = self.snapshot_repo.get(user_id, rec_type)
            if existing:
                existing.inputs_hash = "invalidated"
                self.db.commit()
