from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from app.models.insight import Insight


class InsightRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, insight_id: int, user_id: int) -> Optional[Insight]:
        stmt = select(Insight).where(Insight.id == insight_id, Insight.user_id == user_id)
        return self.db.scalars(stmt).first()

    def list_active(
        self,
        user_id: int,
        engine: Optional[str] = None,
        effort: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Insight]:
        sort_key = case(
            (Insight.impact_annual_cents > 0, Insight.impact_annual_cents),
            else_=Insight.impact_one_time_cents,
        )
        stmt = (
            select(Insight)
            .where(Insight.user_id == user_id, Insight.status == "active")
            .order_by(sort_key.desc(), Insight.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if engine:
            stmt = stmt.where(Insight.engine == engine)
        if effort:
            stmt = stmt.where(Insight.effort == effort)
        return list(self.db.scalars(stmt).all())

    def list_history(self, user_id: int, limit: int = 50, offset: int = 0) -> list[Insight]:
        stmt = (
            select(Insight)
            .where(
                Insight.user_id == user_id,
                Insight.status.in_(["dismissed", "expired", "acted_on"]),
            )
            .order_by(Insight.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all())

    def summary(self, user_id: int) -> dict:
        stmt = select(Insight).where(Insight.user_id == user_id, Insight.status == "active")
        rows = list(self.db.scalars(stmt).all())

        by_engine: dict[str, int] = {}
        total_annual = 0
        unread = 0
        for r in rows:
            by_engine[r.engine] = by_engine.get(r.engine, 0) + 1
            total_annual += r.impact_annual_cents if r.impact_annual_cents else r.impact_one_time_cents
            if r.seen_at is None:
                unread += 1

        return {
            "total_active": len(rows),
            "total_annual_impact_cents": total_annual,
            "unread_count": unread,
            "by_engine": by_engine,
        }

    def dismiss(self, insight: Insight, reason: Optional[str] = None) -> None:
        insight.status = "dismissed"
        insight.dismissed_at = datetime.now(timezone.utc)
        insight.dismissed_inputs_hash = insight.inputs_hash
        self.db.commit()

    def snooze(self, insight: Insight, until: date) -> None:
        insight.status = "snoozed"
        insight.snoozed_until = until
        self.db.commit()

    def mark_acted_on(self, insight: Insight) -> None:
        insight.status = "acted_on"
        self.db.commit()

    def mark_seen(self, user_id: int) -> int:
        now = datetime.now(timezone.utc)
        stmt = (
            update(Insight)
            .where(Insight.user_id == user_id, Insight.status == "active", Insight.seen_at.is_(None))
            .values(seen_at=now)
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount

    def wake_snoozed(self, user_id: int) -> int:
        today = date.today()
        stmt = (
            update(Insight)
            .where(
                Insight.user_id == user_id,
                Insight.status == "snoozed",
                Insight.snoozed_until <= today,
            )
            .values(status="active", snoozed_until=None)
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount

    def find_dismissed_by_kind(
        self, user_id: int, engine: str, kind: str
    ) -> Optional[Insight]:
        stmt = (
            select(Insight)
            .where(
                Insight.user_id == user_id,
                Insight.engine == engine,
                Insight.kind == kind,
                Insight.status == "dismissed",
            )
            .order_by(Insight.dismissed_at.desc())
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def get_active_by_engine(self, user_id: int, engine: str) -> list[Insight]:
        stmt = (
            select(Insight)
            .where(Insight.user_id == user_id, Insight.engine == engine, Insight.status == "active")
        )
        return list(self.db.scalars(stmt).all())

    def expire(self, insight: Insight) -> None:
        insight.status = "expired"
        self.db.commit()

    def upsert_draft(
        self,
        user_id: int,
        engine: str,
        kind: str,
        title: str,
        body: str,
        impact_one_time_cents: int,
        impact_annual_cents: int,
        effort: str,
        evidence_json: str,
        action_json: Optional[str],
        related_goal_id: Optional[int],
        inputs_hash: str,
    ) -> Insight:
        stmt = select(Insight).where(
            Insight.user_id == user_id,
            Insight.engine == engine,
            Insight.kind == kind,
            Insight.inputs_hash == inputs_hash,
        )
        existing = self.db.scalars(stmt).first()
        if existing:
            existing.title = title
            existing.body = body
            existing.impact_one_time_cents = impact_one_time_cents
            existing.impact_annual_cents = impact_annual_cents
            existing.effort = effort
            existing.evidence_json = evidence_json
            existing.action_json = action_json
            existing.related_goal_id = related_goal_id
            self.db.commit()
            self.db.refresh(existing)
            return existing

        row = Insight(
            user_id=user_id,
            engine=engine,
            kind=kind,
            title=title,
            body=body,
            impact_one_time_cents=impact_one_time_cents,
            impact_annual_cents=impact_annual_cents,
            effort=effort,
            evidence_json=evidence_json,
            action_json=action_json,
            related_goal_id=related_goal_id,
            status="active",
            inputs_hash=inputs_hash,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
