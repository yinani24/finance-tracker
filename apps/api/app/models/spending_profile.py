from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SpendingProfile(Base):
    __tablename__ = "spending_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_spending_profiles_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    avg_monthly_spend: Mapped[float] = mapped_column(Float, default=0.0)
    category_breakdown_json: Mapped[str] = mapped_column(Text, default="{}")
    category_counts_json: Mapped[str] = mapped_column(
        Text, default="{}", server_default="{}"
    )
    top_merchants_json: Mapped[str] = mapped_column(Text, default="[]")
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
