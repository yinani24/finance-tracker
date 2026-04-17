import json
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.insight import Insight


def test_create_insight(db_session: Session, seed_user):
    insight = Insight(
        user_id=seed_user.id,
        engine="save",
        kind="idle_cash",
        title="Move $8,400 to HYSA",
        body="Your checking account has averaged $8,400 over 90 days.",
        impact_one_time_cents=0,
        impact_annual_cents=35700,
        effort="low",
        evidence_json=json.dumps({"summary": "test", "data_points": []}),
        action_json=json.dumps({"label": "Open HYSA", "kind": "external", "target": "https://example.com"}),
        status="active",
        inputs_hash="abc123",
    )
    db_session.add(insight)
    db_session.commit()
    db_session.refresh(insight)

    assert insight.id is not None
    assert insight.engine == "save"
    assert insight.kind == "idle_cash"
    assert insight.impact_annual_cents == 35700
    assert insight.status == "active"
    assert insight.created_at is not None


def test_unique_constraint_prevents_duplicates(db_session: Session, seed_user):
    kwargs = dict(
        user_id=seed_user.id,
        engine="save",
        kind="idle_cash",
        title="Move $8,400 to HYSA",
        body="test",
        impact_one_time_cents=0,
        impact_annual_cents=35700,
        effort="low",
        evidence_json="{}",
        status="active",
        inputs_hash="same_hash",
    )
    db_session.add(Insight(**kwargs))
    db_session.commit()

    db_session.add(Insight(**kwargs))
    from sqlalchemy.exc import IntegrityError
    import pytest
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_nullable_fields_default(db_session: Session, seed_user):
    insight = Insight(
        user_id=seed_user.id,
        engine="card",
        kind="next_card",
        title="Get Chase Sapphire",
        body="test",
        impact_one_time_cents=60000,
        impact_annual_cents=0,
        effort="medium",
        evidence_json="{}",
        status="active",
        inputs_hash="xyz789",
    )
    db_session.add(insight)
    db_session.commit()
    db_session.refresh(insight)

    assert insight.action_json is None
    assert insight.related_goal_id is None
    assert insight.snoozed_until is None
    assert insight.dismissed_at is None
    assert insight.dismissed_inputs_hash is None
    assert insight.seen_at is None
