from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recommendation_snapshot import RecommendationSnapshot


class RecommendationSnapshotRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int, rec_type: str) -> Optional[RecommendationSnapshot]:
        stmt = select(RecommendationSnapshot).where(
            RecommendationSnapshot.user_id == user_id,
            RecommendationSnapshot.type == rec_type,
        )
        return self.db.scalars(stmt).first()

    def upsert(self, user_id: int, rec_type: str, results_json: str,
               inputs_hash: str) -> RecommendationSnapshot:
        existing = self.get(user_id, rec_type)
        if existing:
            existing.results_json = results_json
            existing.inputs_hash = inputs_hash
            existing.computed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        snap = RecommendationSnapshot(
            user_id=user_id, type=rec_type, results_json=results_json,
            inputs_hash=inputs_hash,
        )
        self.db.add(snap)
        self.db.commit()
        self.db.refresh(snap)
        return snap
