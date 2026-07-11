from typing import Literal, Optional

from sqlalchemy.orm import Session

from app.models.insight import Insight
from app.repositories.insight import InsightRepository
from app.services.insight_dispatcher import InsightDispatcher
from app.services.insight_types import (
    EngineContext,
    EngineEvent,
    InsightDraft,
)


class FakeEngine:
    name = "test_engine"

    def __init__(self, drafts: Optional[list[InsightDraft]] = None, should_raise: bool = False):
        self._drafts = drafts or []
        self._should_raise = should_raise

    def relevant_events(self) -> set[EngineEvent]:
        return {EngineEvent.TRANSACTIONS_SYNCED}

    def generate(self, user_id: int, ctx: EngineContext) -> list[InsightDraft]:
        if self._should_raise:
            raise RuntimeError("engine crashed")
        return self._drafts

    def detect_resolution(
        self, old_insight: Insight, ctx: EngineContext
    ) -> Literal["acted_on", "expired", "still_active"]:
        return "expired"


def _draft(kind="test_kind", hash_val="h1", annual=10000) -> InsightDraft:
    return InsightDraft(
        kind=kind,
        title=f"Test {kind}",
        body="test body",
        impact_one_time_cents=0,
        impact_annual_cents=annual,
        effort="low",
        evidence={"summary": "test", "data_points": []},
        action=None,
        related_goal_id=None,
        inputs_hash=hash_val,
    )


def test_fire_creates_insights(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft()])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)
    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)
    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id)
    assert len(results) == 1
    assert results[0].engine == "test_engine"
    assert results[0].kind == "test_kind"


def test_fire_skips_irrelevant_engines(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft()])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)
    dispatcher.fire(EngineEvent.GOAL_MUTATED, seed_user.id)
    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id)
    assert len(results) == 0


def test_fire_isolates_engine_failure(db_session: Session, seed_user):
    good_engine = FakeEngine(drafts=[_draft(hash_val="good")])
    good_engine.name = "good_engine"
    bad_engine = FakeEngine(should_raise=True)
    bad_engine.name = "bad_engine"
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(good_engine)
    dispatcher.register(bad_engine)
    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)
    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id)
    assert len(results) == 1
    assert results[0].engine == "good_engine"


def test_fire_expires_missing_drafts(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft()])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)
    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)
    engine._drafts = []
    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)
    repo = InsightRepository(db_session)
    active = repo.list_active(seed_user.id)
    assert len(active) == 0
    history = repo.list_history(seed_user.id)
    assert len(history) == 1
    assert history[0].status == "expired"


def test_fire_keeps_matching_drafts(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft()])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)
    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)
    repo = InsightRepository(db_session)
    first_id = repo.list_active(seed_user.id)[0].id
    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)
    results = repo.list_active(seed_user.id)
    assert len(results) == 1
    assert results[0].id == first_id


def test_fire_all_runs_every_engine(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft()])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)
    dispatcher.fire_all(seed_user.id)
    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id)
    assert len(results) == 1


def test_fire_respects_dismissed_sticky(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft()])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)
    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)
    repo = InsightRepository(db_session)
    insight = repo.list_active(seed_user.id)[0]
    repo.dismiss(insight)
    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)
    active = repo.list_active(seed_user.id)
    assert len(active) == 0


def test_fire_resurfaces_after_material_change(db_session: Session, seed_user):
    engine = FakeEngine(drafts=[_draft(hash_val="v1", annual=10000)])
    dispatcher = InsightDispatcher(db_session)
    dispatcher.register(engine)
    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)
    repo = InsightRepository(db_session)
    insight = repo.list_active(seed_user.id)[0]
    repo.dismiss(insight)
    engine._drafts = [_draft(hash_val="v2", annual=15000)]
    dispatcher.fire(EngineEvent.TRANSACTIONS_SYNCED, seed_user.id)
    active = repo.list_active(seed_user.id)
    assert len(active) == 1
    assert active[0].impact_annual_cents == 15000
