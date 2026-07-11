from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.card import Card
from app.models.goal import Goal
from app.models.plaid_item import PlaidItem
from app.models.transaction import Transaction
from app.repositories.insight import InsightRepository
from app.services.insight_types import (
    EngineContext,
    EngineEvent,
    InsightDraft,
    InsightEngine,
)
from app.services.spending_profile import get_or_refresh

logger = logging.getLogger(__name__)

DISMISS_STICKY_DAYS = 90
DISMISS_RESURFACE_THRESHOLD = 0.25


class InsightDispatcher:
    def __init__(self, db: Session):
        self.db = db
        self._engines: list[InsightEngine] = []

    def register(self, engine: InsightEngine) -> None:
        self._engines.append(engine)

    def fire(self, event: EngineEvent, user_id: int) -> None:
        engines = [e for e in self._engines if event in e.relevant_events()]
        if not engines:
            return
        ctx = self._build_context(user_id)
        for engine in engines:
            self._run_engine(engine, user_id, ctx)

    def fire_all(self, user_id: int) -> None:
        if not self._engines:
            return
        ctx = self._build_context(user_id)
        for engine in self._engines:
            self._run_engine(engine, user_id, ctx)

    def _build_context(self, user_id: int) -> EngineContext:
        try:
            profile = get_or_refresh(self.db, user_id)
        except Exception:
            profile = None

        accounts = list(self.db.scalars(
            select(Account).where(Account.user_id == user_id)
        ).all())
        cards = list(self.db.scalars(
            select(Card).where(Card.user_id == user_id)
        ).all())
        goals = list(self.db.scalars(
            select(Goal).where(Goal.user_id == user_id)
        ).all())
        plaid_items = list(self.db.scalars(
            select(PlaidItem).where(PlaidItem.user_id == user_id)
        ).all())
        transactions = list(self.db.scalars(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.occurred_on.desc())
            .limit(500)
        ).all())

        return EngineContext(
            spending_profile=profile,
            accounts=accounts,
            cards=cards,
            goals=goals,
            plaid_items=plaid_items,
            transactions_recent=transactions,
        )

    def _run_engine(self, engine: InsightEngine, user_id: int, ctx: EngineContext) -> None:
        try:
            drafts = engine.generate(user_id, ctx)
        except Exception:
            logger.exception("Insight engine '%s' failed for user %d", engine.name, user_id)
            return

        repo = InsightRepository(self.db)
        existing = repo.get_active_by_engine(user_id, engine.name)
        existing_by_hash = {row.inputs_hash: row for row in existing}

        new_hashes: set[str] = set()
        for draft in drafts:
            new_hashes.add(draft.inputs_hash)
            if draft.inputs_hash in existing_by_hash:
                row = existing_by_hash[draft.inputs_hash]
                row.title = draft.title
                row.body = draft.body
                row.impact_one_time_cents = draft.impact_one_time_cents
                row.impact_annual_cents = draft.impact_annual_cents
                row.effort = draft.effort
                row.evidence_json = json.dumps(draft.evidence)
                row.action_json = json.dumps(draft.action) if draft.action else None
                row.related_goal_id = draft.related_goal_id
                continue

            if self._is_dismissed_sticky(repo, user_id, engine.name, draft):
                continue

            repo.upsert_draft(
                user_id=user_id,
                engine=engine.name,
                kind=draft.kind,
                title=draft.title,
                body=draft.body,
                impact_one_time_cents=draft.impact_one_time_cents,
                impact_annual_cents=draft.impact_annual_cents,
                effort=draft.effort,
                evidence_json=json.dumps(draft.evidence),
                action_json=json.dumps(draft.action) if draft.action else None,
                related_goal_id=draft.related_goal_id,
                inputs_hash=draft.inputs_hash,
            )

        for old_hash, old_row in existing_by_hash.items():
            if old_hash not in new_hashes:
                try:
                    resolution = engine.detect_resolution(old_row, ctx)
                except Exception:
                    resolution = "expired"
                if resolution == "acted_on":
                    repo.mark_acted_on(old_row)
                elif resolution == "expired":
                    repo.expire(old_row)

        self.db.commit()

    def _is_dismissed_sticky(
        self,
        repo: InsightRepository,
        user_id: int,
        engine_name: str,
        draft: InsightDraft,
    ) -> bool:
        dismissed = repo.find_dismissed_by_kind(user_id, engine_name, draft.kind)
        if dismissed is None:
            return False

        now = datetime.now(timezone.utc)
        dismissed_at = dismissed.dismissed_at
        if dismissed_at and dismissed_at.tzinfo is None:
            dismissed_at = dismissed_at.replace(tzinfo=timezone.utc)

        if dismissed_at and (now - dismissed_at) > timedelta(days=DISMISS_STICKY_DAYS):
            return False

        old_impact = dismissed.impact_annual_cents or dismissed.impact_one_time_cents
        new_impact = draft.impact_annual_cents or draft.impact_one_time_cents
        if old_impact > 0:
            change_ratio = abs(new_impact - old_impact) / old_impact
            if change_ratio >= DISMISS_RESURFACE_THRESHOLD:
                return False

        return True
