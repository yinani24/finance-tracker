from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.config import settings
from app.services.approval_odds import ApprovalProfile
from app.services.card_recommendation import CardRecommendationService
from app.services.recommendation_snapshot import (
    RecommendationSnapshotService,
    _fetch_cards,
)
from app.services.spending_profile import _months_spanned, get_or_refresh

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/next-card")
def get_next_card(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    service = RecommendationSnapshotService(db)
    return service.get_recommendations(user_id, "next_card")


@router.get("/portfolio")
def get_portfolio(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    service = RecommendationSnapshotService(db)
    return service.get_recommendations(user_id, "portfolio_gap")


@router.get("/spending-profile")
def get_spending_profile(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    profile = get_or_refresh(db, user_id)

    breakdown = json.loads(profile.category_breakdown_json)
    counts = json.loads(profile.category_counts_json)
    # Reuse the exact divisor compute_profile used, so monthly-avg-count and
    # avg-per-txn stay consistent with the stored monthly-avg dollars.
    months = _months_spanned(profile.period_start, profile.period_end)

    categories = []
    for cat, monthly_avg in breakdown.items():
        cnt = counts.get(cat, 0)
        # Reconstruct total $ from the stored monthly average to derive avg ticket.
        monthly_total = monthly_avg * months
        categories.append(
            {
                "category": cat,
                "monthly_avg": monthly_avg,  # unchanged key
                "count": cnt,
                "monthly_avg_count": round(cnt / months, 2),
                "avg_per_txn": round(monthly_total / cnt, 2) if cnt else 0.0,
            }
        )

    dining = next((c for c in categories if c["category"] == "dining"), None)

    return {
        "user_id": profile.user_id,
        "period_start": str(profile.period_start),
        "period_end": str(profile.period_end),
        "avg_monthly_spend": profile.avg_monthly_spend,
        "categories": categories,
        "dining": dining,
        "top_merchants": json.loads(profile.top_merchants_json),
        "computed_at": str(profile.computed_at),
    }


@router.post("/refresh")
def refresh_recommendations(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    service = RecommendationSnapshotService(db)
    service.invalidate(user_id)
    service.get_recommendations(user_id, "next_card")
    service.get_recommendations(user_id, "portfolio_gap")
    return {"status": "refreshed"}


class StatelessCard(BaseModel):
    """A card the user holds, as read out of their own statement."""

    name: str
    issuer: str | None = None
    annual_fee: float = 0.0


class StatelessProfileRequest(BaseModel):
    """Aggregates the browser derived from statements it parsed locally.

    Deliberately aggregate-only: monthly spend and a category breakdown are
    enough for the ranking engine, so no merchant names, dates, amounts or
    account numbers ever leave the user's device. Nothing here is written to the
    database — the request is computed and discarded.
    """

    avg_monthly_spend: float = 0.0
    category_breakdown: dict[str, float] = Field(default_factory=dict)
    held_cards: list[StatelessCard] = Field(default_factory=list)
    credit_score_band: str | None = None
    recent_card_applications: int | None = None
    max_results: int = 10


@router.post("/next-card/stateless")
def post_next_card_stateless(payload: StatelessProfileRequest) -> dict:
    """Rank cards from a profile supplied in the request.

    The GET counterpart reads the caller's stored transactions, which is wrong
    for the client-only flow: statements are parsed in the browser and never
    reach the database, so the stored profile is either empty or stale test
    data. This endpoint takes the profile as input instead. It touches no
    session, no user row and no table.
    """
    service = CardRecommendationService()
    approval_profile = ApprovalProfile(
        score_band=payload.credit_score_band,
        recent_applications=payload.recent_card_applications,
    )

    recommendations = service.recommend_next_card(
        {
            "avg_monthly_spend": payload.avg_monthly_spend,
            "category_breakdown": payload.category_breakdown,
            "top_merchants": [],
        },
        [
            {
                "name": c.name,
                "issuer": c.issuer or "",
                "network": "",
                "annual_fee": c.annual_fee,
            }
            for c in payload.held_cards
        ],
        _fetch_cards(),
        max_results=payload.max_results,
        points_value_cents=settings.points_value_cents,
        approval_profile=approval_profile,
    )
    return {"recommendations": recommendations}


@router.post("/portfolio/stateless")
def post_portfolio_stateless(payload: StatelessProfileRequest) -> dict:
    """Analyse the cards the user holds, from a profile supplied in the request.

    Same contract as ``post_next_card_stateless``: aggregates in, analysis out,
    nothing persisted. Returns both the per-card value analysis and the
    per-category "use this card here" assignments, which are computed from the
    same profile so the two can't disagree.
    """
    service = CardRecommendationService()
    profile = {
        "avg_monthly_spend": payload.avg_monthly_spend,
        "category_breakdown": payload.category_breakdown,
        "top_merchants": [],
    }
    user_cards = [
        {
            "name": c.name,
            "issuer": c.issuer or "",
            "network": "",
            "annual_fee": c.annual_fee,
        }
        for c in payload.held_cards
    ]
    available = _fetch_cards()
    return {
        "analyses": service.analyze_portfolio(profile, user_cards, available),
        "best_per_category": service.best_card_per_category(
            profile, user_cards, available
        ),
    }
