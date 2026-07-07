from __future__ import annotations

import hashlib
import json
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

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


def _compute_inputs_hash(profile_json: str, cards_json: str) -> str:
    raw = f"{profile_json}|{cards_json}"
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

    def get_recommendations(self, user_id: int, rec_type: str) -> Dict:
        profile = get_or_refresh_profile(self.db, user_id)
        user_cards = self._get_user_cards(user_id)

        profile_json = profile.category_breakdown_json + str(profile.avg_monthly_spend)
        cards_json = json.dumps(user_cards, sort_keys=True)
        current_hash = _compute_inputs_hash(profile_json, cards_json)

        # Check cache
        existing = self.snapshot_repo.get(user_id, rec_type)
        if existing and existing.inputs_hash == current_hash:
            result_key = "recommendations" if rec_type == "next_card" else "cards"
            return {
                result_key: json.loads(existing.results_json),
                "spending_profile": self._profile_to_read(profile),
            }

        # Recompute
        available_cards = _fetch_cards()
        profile_dict = {
            "avg_monthly_spend": profile.avg_monthly_spend,
            "category_breakdown": json.loads(profile.category_breakdown_json),
            "top_merchants": json.loads(profile.top_merchants_json),
        }

        if rec_type == "next_card":
            results = self.rec_service.recommend_next_card(
                profile_dict, user_cards, available_cards
            )
            result_key = "recommendations"
        else:
            results = self.rec_service.analyze_portfolio(
                profile_dict, user_cards, available_cards
            )
            result_key = "cards"

        self.snapshot_repo.upsert(
            user_id=user_id,
            rec_type=rec_type,
            results_json=json.dumps(results),
            inputs_hash=current_hash,
        )

        return {
            result_key: results,
            "spending_profile": self._profile_to_read(profile),
        }

    def invalidate(self, user_id: int) -> None:
        for rec_type in ("next_card", "portfolio_gap"):
            existing = self.snapshot_repo.get(user_id, rec_type)
            if existing:
                existing.inputs_hash = "invalidated"
                self.db.commit()
