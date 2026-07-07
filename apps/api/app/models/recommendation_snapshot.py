from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RecommendationSnapshot(Base):
    __tablename__ = "recommendation_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "type", name="uq_recommendation_snapshots_user_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    results_json: Mapped[str] = mapped_column(Text, default="[]")
    inputs_hash: Mapped[str] = mapped_column(String(64))
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
