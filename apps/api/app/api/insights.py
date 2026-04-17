from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.repositories.insight import InsightRepository
from app.schemas.insight import (
    DismissRequest,
    InsightRead,
    InsightSummary,
    MarkSeenResponse,
    SnoozeRequest,
)
from app.services.insight_dispatcher import InsightDispatcher
from app.services.insight_types import EngineEvent

router = APIRouter(prefix="/insights", tags=["insights"])


def get_default_dispatcher(db: Session) -> InsightDispatcher:
    from app.services.card_insight_engine import CardInsightEngine

    dispatcher = InsightDispatcher(db)
    dispatcher.register(CardInsightEngine())
    return dispatcher


def fire_insights_event(db: Session, event: EngineEvent, user_id: int) -> None:
    dispatcher = get_default_dispatcher(db)
    dispatcher.fire(event, user_id)


@router.get("", response_model=list[InsightRead])
def list_insights(
    engine: Optional[str] = None,
    effort: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[InsightRead]:
    repo = InsightRepository(db)
    repo.wake_snoozed(user_id)
    return repo.list_active(user_id, engine=engine, effort=effort, limit=limit, offset=offset)


@router.get("/summary", response_model=InsightSummary)
def get_summary(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> InsightSummary:
    repo = InsightRepository(db)
    repo.wake_snoozed(user_id)
    return repo.summary(user_id)


@router.get("/history", response_model=list[InsightRead])
def list_history(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[InsightRead]:
    repo = InsightRepository(db)
    return repo.list_history(user_id, limit=limit, offset=offset)


@router.get("/{insight_id}", response_model=InsightRead)
def get_insight(
    insight_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> InsightRead:
    repo = InsightRepository(db)
    row = repo.get(insight_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Insight not found")
    return row


@router.post("/{insight_id}/dismiss", response_model=InsightRead)
def dismiss_insight(
    insight_id: int,
    body: DismissRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> InsightRead:
    repo = InsightRepository(db)
    row = repo.get(insight_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Insight not found")
    repo.dismiss(row, reason=body.reason)
    return row


@router.post("/{insight_id}/snooze", response_model=InsightRead)
def snooze_insight(
    insight_id: int,
    body: SnoozeRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> InsightRead:
    repo = InsightRepository(db)
    row = repo.get(insight_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Insight not found")
    repo.snooze(row, body.until)
    return row


@router.post("/{insight_id}/acted-on", response_model=InsightRead)
def mark_acted_on(
    insight_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> InsightRead:
    repo = InsightRepository(db)
    row = repo.get(insight_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Insight not found")
    repo.mark_acted_on(row)
    return row


@router.post("/mark-seen", response_model=MarkSeenResponse)
def mark_seen(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> MarkSeenResponse:
    repo = InsightRepository(db)
    count = repo.mark_seen(user_id)
    return MarkSeenResponse(marked=count)


@router.post("/refresh")
def refresh_insights(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> dict:
    dispatcher = get_default_dispatcher(db)
    dispatcher.fire_all(user_id)
    return {"status": "refreshed"}
