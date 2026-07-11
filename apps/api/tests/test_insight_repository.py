import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.insight import Insight
from app.repositories.insight import InsightRepository


def _make_insight(db: Session, user_id: int, **overrides) -> Insight:
    defaults = dict(
        user_id=user_id,
        engine="save",
        kind="idle_cash",
        title="Test insight",
        body="Test body",
        impact_one_time_cents=0,
        impact_annual_cents=10000,
        effort="low",
        evidence_json=json.dumps({"summary": "test", "data_points": []}),
        status="active",
        inputs_hash="hash_default",
    )
    defaults.update(overrides)
    row = Insight(**defaults)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_list_active_returns_only_active(db_session: Session, seed_user):
    _make_insight(db_session, seed_user.id, inputs_hash="h1")
    _make_insight(db_session, seed_user.id, inputs_hash="h2", status="dismissed")
    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id)
    assert len(results) == 1
    assert results[0].status == "active"


def test_list_active_sorted_by_annual_then_one_time(db_session: Session, seed_user):
    _make_insight(
        db_session, seed_user.id, inputs_hash="h1",
        impact_annual_cents=5000, impact_one_time_cents=0,
    )
    _make_insight(
        db_session, seed_user.id, inputs_hash="h2",
        impact_annual_cents=20000, impact_one_time_cents=0,
    )
    _make_insight(
        db_session, seed_user.id, inputs_hash="h3",
        impact_annual_cents=0, impact_one_time_cents=90000,
    )
    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id)
    assert [r.inputs_hash for r in results] == ["h3", "h2", "h1"]


def test_list_active_filters_by_engine(db_session: Session, seed_user):
    _make_insight(db_session, seed_user.id, inputs_hash="h1", engine="save")
    _make_insight(db_session, seed_user.id, inputs_hash="h2", engine="card")
    repo = InsightRepository(db_session)
    results = repo.list_active(seed_user.id, engine="save")
    assert len(results) == 1
    assert results[0].engine == "save"


def test_get_by_id(db_session: Session, seed_user):
    row = _make_insight(db_session, seed_user.id)
    repo = InsightRepository(db_session)
    found = repo.get(row.id, seed_user.id)
    assert found is not None
    assert found.id == row.id


def test_get_by_id_wrong_user_returns_none(db_session: Session, seed_user):
    row = _make_insight(db_session, seed_user.id)
    repo = InsightRepository(db_session)
    assert repo.get(row.id, 9999) is None


def test_dismiss(db_session: Session, seed_user):
    row = _make_insight(db_session, seed_user.id)
    repo = InsightRepository(db_session)
    repo.dismiss(row, reason="not useful")
    db_session.refresh(row)
    assert row.status == "dismissed"
    assert row.dismissed_at is not None
    assert row.dismissed_inputs_hash == row.inputs_hash


def test_snooze(db_session: Session, seed_user):
    row = _make_insight(db_session, seed_user.id)
    repo = InsightRepository(db_session)
    until = date.today() + timedelta(days=30)
    repo.snooze(row, until)
    db_session.refresh(row)
    assert row.status == "snoozed"
    assert row.snoozed_until == until


def test_mark_acted_on(db_session: Session, seed_user):
    row = _make_insight(db_session, seed_user.id)
    repo = InsightRepository(db_session)
    repo.mark_acted_on(row)
    db_session.refresh(row)
    assert row.status == "acted_on"


def test_mark_seen(db_session: Session, seed_user):
    _make_insight(db_session, seed_user.id, inputs_hash="h1")
    _make_insight(db_session, seed_user.id, inputs_hash="h2")
    repo = InsightRepository(db_session)
    count = repo.mark_seen(seed_user.id)
    assert count == 2


def test_wake_snoozed(db_session: Session, seed_user):
    yesterday = date.today() - timedelta(days=1)
    tomorrow = date.today() + timedelta(days=1)
    _make_insight(
        db_session, seed_user.id, inputs_hash="h1", status="snoozed", snoozed_until=yesterday
    )
    _make_insight(
        db_session, seed_user.id, inputs_hash="h2", status="snoozed", snoozed_until=tomorrow
    )
    repo = InsightRepository(db_session)
    woke = repo.wake_snoozed(seed_user.id)
    assert woke == 1
    results = repo.list_active(seed_user.id)
    assert len(results) == 1
    assert results[0].inputs_hash == "h1"


def test_summary(db_session: Session, seed_user):
    _make_insight(
        db_session, seed_user.id, inputs_hash="h1", engine="save", impact_annual_cents=10000
    )
    _make_insight(
        db_session, seed_user.id, inputs_hash="h2", engine="card", impact_annual_cents=5000
    )
    _make_insight(
        db_session, seed_user.id, inputs_hash="h3", engine="save",
        impact_annual_cents=3000, seen_at=datetime.now(timezone.utc),
    )
    repo = InsightRepository(db_session)
    summary = repo.summary(seed_user.id)
    assert summary["total_active"] == 3
    assert summary["total_annual_impact_cents"] == 18000
    assert summary["unread_count"] == 2
    assert summary["by_engine"]["save"] == 2
    assert summary["by_engine"]["card"] == 1


def test_list_history(db_session: Session, seed_user):
    _make_insight(db_session, seed_user.id, inputs_hash="h1", status="active")
    _make_insight(db_session, seed_user.id, inputs_hash="h2", status="dismissed")
    _make_insight(db_session, seed_user.id, inputs_hash="h3", status="acted_on")
    repo = InsightRepository(db_session)
    history = repo.list_history(seed_user.id)
    assert len(history) == 2
    statuses = {r.status for r in history}
    assert statuses == {"dismissed", "acted_on"}


def test_find_dismissed_by_kind(db_session: Session, seed_user):
    _make_insight(
        db_session, seed_user.id, inputs_hash="h1", status="dismissed",
        dismissed_inputs_hash="old_hash",
        dismissed_at=datetime.now(timezone.utc),
    )
    repo = InsightRepository(db_session)
    found = repo.find_dismissed_by_kind(seed_user.id, "save", "idle_cash")
    assert found is not None
    assert found.dismissed_inputs_hash == "old_hash"


def test_upsert_draft_creates_new(db_session: Session, seed_user):
    repo = InsightRepository(db_session)
    row = repo.upsert_draft(
        user_id=seed_user.id,
        engine="save",
        kind="idle_cash",
        title="Move money",
        body="body",
        impact_one_time_cents=0,
        impact_annual_cents=35000,
        effort="low",
        evidence_json="{}",
        action_json=None,
        related_goal_id=None,
        inputs_hash="new_hash",
    )
    assert row.id is not None
    assert row.status == "active"


def test_upsert_draft_updates_existing(db_session: Session, seed_user):
    repo = InsightRepository(db_session)
    row1 = repo.upsert_draft(
        user_id=seed_user.id, engine="save", kind="idle_cash", title="Old title",
        body="body", impact_one_time_cents=0, impact_annual_cents=35000, effort="low",
        evidence_json="{}", action_json=None, related_goal_id=None, inputs_hash="same_hash",
    )
    row2 = repo.upsert_draft(
        user_id=seed_user.id, engine="save", kind="idle_cash", title="New title",
        body="body", impact_one_time_cents=0, impact_annual_cents=40000, effort="low",
        evidence_json="{}", action_json=None, related_goal_id=None, inputs_hash="same_hash",
    )
    assert row2.id == row1.id
    assert row2.title == "New title"
    assert row2.impact_annual_cents == 40000
