from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Insight(Base):
    __tablename__ = "insights"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "engine",
            "kind",
            "inputs_hash",
            name="uq_insights_user_engine_kind_hash",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    engine: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    impact_one_time_cents: Mapped[int] = mapped_column(Integer, default=0)
    impact_annual_cents: Mapped[int] = mapped_column(Integer, default=0)
    effort: Mapped[str] = mapped_column(String(10))
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    action_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    related_goal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("goals.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="active")
    snoozed_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    dismissed_inputs_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    inputs_hash: Mapped[str] = mapped_column(String(64))
    seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
