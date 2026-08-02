import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.insight import Insight
from app.schemas.insight import SnoozeRequest


def _create_insight(db: Session, user_id: int, **overrides) -> Insight:
    defaults = dict(
        user_id=user_id,
        engine="save",
        kind="idle_cash",
        title="Move money to HYSA",
        body="Your checking has excess cash",
        impact_one_time_cents=0,
        impact_annual_cents=35000,
        effort="low",
        evidence_json=json.dumps({"summary": "test", "data_points": []}),
        status="active",
        inputs_hash="default_hash",
    )
    defaults.update(overrides)
    row = Insight(**defaults)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_list_insights(client: TestClient, db_session: Session, seed_user):
    _create_insight(db_session, seed_user.id, inputs_hash="h1")
    _create_insight(db_session, seed_user.id, inputs_hash="h2", status="dismissed")
    resp = client.get("/insights")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1


def test_list_insights_filter_engine(client: TestClient, db_session: Session, seed_user):
    _create_insight(db_session, seed_user.id, inputs_hash="h1", engine="save")
    _create_insight(db_session, seed_user.id, inputs_hash="h2", engine="card")
    resp = client.get("/insights?engine=save")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_insight(client: TestClient, db_session: Session, seed_user):
    row = _create_insight(db_session, seed_user.id)
    resp = client.get(f"/insights/{row.id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Move money to HYSA"


def test_get_insight_not_found(client: TestClient, seed_user):
    resp = client.get("/insights/99999")
    assert resp.status_code == 404


def test_summary(client: TestClient, db_session: Session, seed_user):
    _create_insight(
        db_session, seed_user.id, inputs_hash="h1", engine="save", impact_annual_cents=10000
    )
    _create_insight(
        db_session, seed_user.id, inputs_hash="h2", engine="card", impact_annual_cents=5000
    )
    resp = client.get("/insights/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_active"] == 2
    assert data["total_annual_impact_cents"] == 15000
    assert data["unread_count"] == 2


def test_dismiss(client: TestClient, db_session: Session, seed_user):
    row = _create_insight(db_session, seed_user.id)
    resp = client.post(f"/insights/{row.id}/dismiss", json={"reason": "not useful"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"


def test_snooze(client: TestClient, db_session: Session, seed_user):
    row = _create_insight(db_session, seed_user.id)
    until = (date.today() + timedelta(days=30)).isoformat()
    resp = client.post(f"/insights/{row.id}/snooze", json={"until": until})
    assert resp.status_code == 200
    assert resp.json()["status"] == "snoozed"


def test_snooze_request_rejects_datetime_accepts_date():
    """Regression for #200: the frontend once sent a full ISO datetime
    (`toISOString()`), which Pydantic v2 rejects for a bare `date` field with a
    non-zero time component → HTTP 422 and a silently-failing snooze button. The
    wire contract is date-only; this pins it so it can't regress."""
    # A datetime string with a non-zero time component must be rejected.
    with pytest.raises(ValidationError):
        SnoozeRequest(until="2026-08-23T14:23:45.123Z")
    # A date-only string is accepted and parses to the expected `date`.
    assert SnoozeRequest(until="2026-08-23").until == date(2026, 8, 23)


def test_acted_on(client: TestClient, db_session: Session, seed_user):
    row = _create_insight(db_session, seed_user.id)
    resp = client.post(f"/insights/{row.id}/acted-on")
    assert resp.status_code == 200
    assert resp.json()["status"] == "acted_on"


def test_mark_seen(client: TestClient, db_session: Session, seed_user):
    _create_insight(db_session, seed_user.id, inputs_hash="h1")
    _create_insight(db_session, seed_user.id, inputs_hash="h2")
    resp = client.post("/insights/mark-seen")
    assert resp.status_code == 200
    assert resp.json()["marked"] == 2


def test_history(client: TestClient, db_session: Session, seed_user):
    _create_insight(db_session, seed_user.id, inputs_hash="h1", status="active")
    _create_insight(db_session, seed_user.id, inputs_hash="h2", status="dismissed")
    _create_insight(db_session, seed_user.id, inputs_hash="h3", status="acted_on")
    resp = client.get("/insights/history")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_refresh(client: TestClient, seed_user):
    resp = client.post("/insights/refresh")
    assert resp.status_code == 200
    assert resp.json()["status"] == "refreshed"
