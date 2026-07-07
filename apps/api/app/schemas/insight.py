from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class InsightRead(BaseModel):
    id: int
    engine: str
    kind: str
    title: str
    body: str
    impact_one_time_cents: int
    impact_annual_cents: int
    effort: str
    evidence_json: str
    action_json: Optional[str]
    related_goal_id: Optional[int]
    status: str
    snoozed_until: Optional[date]
    seen_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InsightSummary(BaseModel):
    total_active: int
    total_annual_impact_cents: int
    unread_count: int
    by_engine: dict[str, int]


class DismissRequest(BaseModel):
    reason: Optional[str] = None


class SnoozeRequest(BaseModel):
    until: date


class MarkSeenResponse(BaseModel):
    marked: int
