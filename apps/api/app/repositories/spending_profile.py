from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.spending_profile import SpendingProfile


class SpendingProfileRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user(self, user_id: int) -> Optional[SpendingProfile]:
        stmt = select(SpendingProfile).where(SpendingProfile.user_id == user_id)
        return self.db.scalars(stmt).first()

    def upsert(self, user_id: int, period_start: date, period_end: date,
               avg_monthly_spend: float, category_breakdown_json: str,
               top_merchants_json: str,
               category_counts_json: str = "{}") -> SpendingProfile:
        existing = self.get_by_user(user_id)
        if existing:
            existing.period_start = period_start
            existing.period_end = period_end
            existing.avg_monthly_spend = avg_monthly_spend
            existing.category_breakdown_json = category_breakdown_json
            existing.category_counts_json = category_counts_json
            existing.top_merchants_json = top_merchants_json
            existing.computed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        profile = SpendingProfile(
            user_id=user_id, period_start=period_start, period_end=period_end,
            avg_monthly_spend=avg_monthly_spend,
            category_breakdown_json=category_breakdown_json,
            category_counts_json=category_counts_json,
            top_merchants_json=top_merchants_json,
        )
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile
