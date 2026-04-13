from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.services.recommendation_snapshot import RecommendationSnapshotService
from app.services.spending_profile import get_or_refresh

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
